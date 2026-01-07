# Copyright 2025 Amazon Inc

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

import functools
import time
from typing import Callable

from nova_act.impl.backends.factory import NovaActBackend
from nova_act.impl.controller import ControlState, NovaStateController
from nova_act.impl.inputs import validate_viewport_dimensions
from nova_act.impl.program.base import Call, Program
from nova_act.impl.program.runner import ProgramRunner, format_return_value
from nova_act.impl.thinker import Thinker
from nova_act.tools.actuator.interface.actuator import ActionType, ActuatorBase
from nova_act.tools.browser.default.util.image_helpers import get_source_image_from_data_url
from nova_act.tools.browser.interface.browser import (
    BrowserActuatorBase,
)
from nova_act.tools.browser.interface.types.agent_redirect_error import (
    AgentRedirectError,
)
from nova_act.tools.human.interface.human_input_callback import HumanInputCallbacksBase
from nova_act.types.act_errors import (
    ActAgentFailed,
    ActCanceledError,
    ActError,
    ActExceededMaxStepsError,
    ActExecutionError,
    ActTimeoutError,
)
from nova_act.types.act_metadata import ActMetadata
from nova_act.types.act_result import ActGetResult
from nova_act.types.errors import ClientNotStarted, ValidationFailed
from nova_act.types.events import EventType, LogType
from nova_act.types.guardrail import GuardrailCallable
from nova_act.types.state.act import Act
from nova_act.util.decode_string import decode_awl_raw_program
from nova_act.util.event_handler import EventHandler
from nova_act.util.human_wait_time_tracker import HumanWaitTimeTracker
from nova_act.util.logging import (
    SessionState,
    get_session_id_prefix,
    make_trace_logger,
    set_logging_session_state,
    setup_logging,
    trace_log_lines,
)

_LOGGER = setup_logging(__name__)
_TRACE_LOGGER = make_trace_logger()

DEFAULT_ENDPOINT_NAME = "alpha-sunshine"


def _handle_act_fail(
    f: Callable[[ActDispatcher, Act], ActGetResult],
) -> Callable[[ActDispatcher, Act], ActGetResult]:
    """Update Act objects with appropriate metadata on Exceptions."""

    @functools.wraps(f)
    def wrapper(self: ActDispatcher, act: Act) -> ActGetResult:
        try:
            return f(self, act)
        except ActError as e:
            # If an ActError is encountered, inject it with metadata.
            act.end_time = act.end_time or time.time()

            # Calculate time worked even for failed acts
            if act.start_time is not None and act.end_time is not None:
                human_wait_time = self._wait_time_tracker.get_total_wait_time_s()
                time_worked = _calculate_time_worked(act.start_time, act.end_time, human_wait_time)

                # Create metadata with time worked for the error
                e.metadata = ActMetadata(
                    session_id=act.session_id,
                    act_id=act.id,
                    num_steps_executed=len(act._steps),
                    start_time=act.start_time,
                    end_time=act.end_time,
                    step_server_times_s=act.get_step_server_times_s,
                    prompt=act.prompt,
                    time_worked_s=time_worked,
                    human_wait_time_s=human_wait_time,
                )
            else:
                e.metadata = e.metadata or act.metadata

            raise e
        finally:
            # Make sure we always set end time.
            act.end_time = act.end_time or time.time()
            set_logging_session_state(SessionState.UNKNOWN)

    return wrapper


def _calculate_time_worked(start_time: float | None, end_time: float | None, human_wait_time_s: float) -> float | None:
    """Calculate time worked with error handling.

    Args:
        start_time: Act start timestamp in seconds since epoch
        end_time: Act end timestamp in seconds since epoch
        human_wait_time_s: Total time spent waiting for human input in seconds

    Returns:
        Time worked in seconds (total duration minus human wait time), or None if timestamps are missing.
        Returns 0.0 if duration is negative or human wait time exceeds total duration.
    """
    if start_time is None or end_time is None:
        return None

    total_duration = end_time - start_time

    if total_duration < 0:
        _LOGGER.warning(
            f"Negative duration detected: end_time ({end_time}) < start_time ({start_time}). "
            "Setting time_worked_s to 0.0"
        )
        return 0.0

    if human_wait_time_s > total_duration:
        _LOGGER.warning(
            f"Human wait time ({human_wait_time_s}s) exceeds total duration ({total_duration}s). "
            "Setting time_worked_s to 0.0"
        )
        return 0.0

    return max(0.0, total_duration - human_wait_time_s)


def _log_time_worked(metadata: ActMetadata) -> None:
    """Log time worked to console with styling.

    Args:
        metadata: ActMetadata containing time worked information
    """
    if metadata.time_worked_s is None:
        return

    # Import _format_duration from act_metadata
    from nova_act.types.act_metadata import _format_duration

    time_worked_str = _format_duration(metadata.time_worked_s)

    if metadata.human_wait_time_s > 0:
        human_wait_str = _format_duration(metadata.human_wait_time_s)
        message = f"⏱️  Approx. Time Worked: {time_worked_str} " f"(excluding {human_wait_str} human wait)"
    else:
        message = f"⏱️  Approx. Time Worked: {time_worked_str}"

    # Use trace logger only (not standard logger to avoid duplication)
    trace_log_lines(message)


class ActDispatcher:
    _actuator: BrowserActuatorBase

    def __init__(
        self,
        actuator: ActuatorBase | None,
        backend: NovaActBackend,
        controller: NovaStateController,
        event_handler: EventHandler,
        human_input_callbacks: HumanInputCallbacksBase,
        tools: list[ActionType] | None = None,
        state_guardrail: GuardrailCallable | None = None,
    ):
        if not isinstance(actuator, BrowserActuatorBase):
            raise ValidationFailed("actuator must be an instance of BrowserActuatorBase")
        self._actuator = actuator
        self._backend = backend
        self._tools = actuator.list_actions().copy()
        self._human_input_callbacks = human_input_callbacks
        self._tools += (tools or []) + human_input_callbacks.as_tools()
        self._tool_map = {tool.tool_name: tool for tool in self._tools}

        self._canceled = False
        self._event_handler = event_handler
        self._controller = controller
        self._program_runner = ProgramRunner(
            self._event_handler,
            state_guardrail,
        )

        # Create wait time tracker and inject into human input callbacks provider
        self._wait_time_tracker = HumanWaitTimeTracker()
        # Inject the tracker into the provider
        self._human_input_callbacks.provider.set_wait_time_tracker(self._wait_time_tracker)

    def _cancel_act(self, act: Act) -> None:
        _TRACE_LOGGER.info(f"\n{get_session_id_prefix()}Terminating agent workflow")
        self._event_handler.send_event(
            type=EventType.LOG,
            log_level=LogType.INFO,
            data="Terminating agent workflow",
        )
        raise ActCanceledError()

    @_handle_act_fail
    def dispatch(self, act: Act) -> ActGetResult:
        """Dispatch an Act with given Backend and Actuator."""

        # Reset wait time tracker for new act
        self._wait_time_tracker.reset()

        if self._backend is None:
            raise ClientNotStarted("Run start() to start the client before accessing the Playwright Page.")


        step_object = None
        step_idx = 0

        # Create and run initial Program
        initial_calls: list[Call] = []
        if act.observation_delay_ms:
            initial_calls.append(Call(name="wait", id="wait", kwargs={"seconds": act.observation_delay_ms / 1000}))
        initial_calls += [
            Call(name="waitForPageToSettle", id="waitForPageToSettle", kwargs={}),
            Call(name="takeObservation", id="takeObservation", kwargs={}),
        ]
        program = Program(calls=initial_calls)
        executable = program.compile(self._tool_map)
        program_result = self._program_runner.run(executable)

        # Make sure initial Program run succeeded
        if exception_result := program_result.has_exception():
            assert exception_result.error is not None  # TODO: improve typing of CallResult
            raise exception_result.error

        with self._controller as control:
            end_time = time.time() + act.timeout

            while True:
                # Check time out / max steps
                if time.time() > end_time:
                    act.did_timeout = True
                    raise ActTimeoutError()

                if step_idx >= act.max_steps:
                    raise ActExceededMaxStepsError(f"Exceeded max steps {act.max_steps} without return.")

                # Optionally warn for dangerous viewport dimensions in BrowserObservations
                if observation := program_result.has_observation():  # ensure we took an observation
                    if browser_observation := self._backend._maybe_observation(  # typeguard BrowserObservation
                        observation.return_value
                    ):
                        screenshot_b64 = browser_observation["screenshotBase64"]
                        screenshot_pil = get_source_image_from_data_url(screenshot_b64)
                        validate_viewport_dimensions(*screenshot_pil.size, warn=act.ignore_screen_dims_check)

                # Get a Program from the model
                set_logging_session_state(SessionState.THINKING)
                with Thinker(tty=self._controller._tty, logger=_TRACE_LOGGER):
                    step_object = self._backend.step(act, program_result.call_results, self._tool_map)

                self._human_input_callbacks.most_recent_screenshot = step_object.model_input.image

                act.add_step(step_object)
                program = step_object.program

                # Log the model output
                awl_program = decode_awl_raw_program(step_object.model_output.awl_raw_program)
                trace_log_lines(awl_program)

                # Handle pause/cancel conditions
                while control.state == ControlState.PAUSED:
                    time.sleep(0.1)

                if control.state == ControlState.CANCELLED:
                    self._cancel_act(act)

                # Compile and run the program
                try:
                    executable = program.compile(self._tool_map)
                    set_logging_session_state(SessionState.UNKNOWN)
                    with Thinker(tty=self._controller._tty, logger=_TRACE_LOGGER):
                        program_result = self._program_runner.run(executable)

                    if throw_result := program_result.has_throw():
                        message = format_return_value(throw_result.return_value)
                        raise ActAgentFailed(message=message)
                    elif exception_result := program_result.has_exception():
                        assert exception_result.error is not None  # TODO: improve typing of CallResult
                        raise exception_result.error

                except AgentRedirectError as e:
                    # Client wants to redirect the agent to try a different action
                    trace_log_lines("AgentRedirect: " + e.error_and_correction)

                if return_result := program_result.has_return():
                    result = return_result.return_value
                    act.complete(str(result) if result is not None else None)
                    break

                step_idx += 1

        if act.result is None:
            raise ActExecutionError("Act completed without a result.")

        self._event_handler.send_event(
            type=EventType.ACTION,
            action="result",
            data=act.result,
        )

        # Calculate and set time worked
        if act.start_time is not None and act.end_time is not None:
            human_wait_time = self._wait_time_tracker.get_total_wait_time_s()
            time_worked = _calculate_time_worked(act.start_time, act.end_time, human_wait_time)

            # Update act metadata with time worked
            # Note: This requires act.set_time_worked() to be implemented (Task 7)
            if hasattr(act, "set_time_worked"):
                act.set_time_worked(time_worked, human_wait_time)

                # Log time worked to console
                _log_time_worked(act.result.metadata)

        return act.result

    def cancel_prompt(self, act: Act | None = None) -> None:
        self._canceled = True
