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
from nova_act.impl.program.base import Call, Program
from nova_act.impl.program.runner import ProgramRunner, format_return_value
from nova_act.tools.actuator.interface.actuator import ActuatorBase
from nova_act.tools.browser.interface.browser import (
    BrowserActuatorBase,
)
from nova_act.tools.browser.interface.types.agent_redirect_error import (
    AgentRedirectError,
)
from nova_act.types.act_errors import (
    ActAgentFailed,
    ActCanceledError,
    ActError,
    ActExceededMaxStepsError,
    ActExecutionError,
    ActTimeoutError,
)
from nova_act.types.act_result import ActGetResult
from nova_act.types.errors import ClientNotStarted, ValidationFailed
from nova_act.types.events import EventType, LogType
from nova_act.types.guardrail import GuardrailCallable
from nova_act.types.state.act import Act
from nova_act.util.decode_string import decode_awl_raw_program
from nova_act.util.event_handler import EventHandler
from nova_act.util.logging import (
    get_session_id_prefix,
    make_trace_logger,
    trace_log_lines,
)

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
            e.metadata = e.metadata or act.metadata
            raise e
        finally:
            # Make sure we always set end time.
            act.end_time = act.end_time or time.time()

    return wrapper


class ActDispatcher:
    _actuator: BrowserActuatorBase

    def __init__(
        self,
        actuator: ActuatorBase | None,
        backend: NovaActBackend,
        controller: NovaStateController,
        event_handler: EventHandler,
        state_guardrail: GuardrailCallable | None = None,
    ):
        if not isinstance(actuator, BrowserActuatorBase):
            raise ValidationFailed("actuator must be an instance of BrowserActuatorBase")
        self._actuator = actuator
        self._backend = backend
        self._tools = actuator.list_actions().copy()
        self._tool_map = {tool.tool_name: tool for tool in self._tools}

        self._canceled = False
        self._event_handler = event_handler
        self._controller = controller
        self._program_runner = ProgramRunner(
            self._event_handler,
            state_guardrail,
        )

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

                # Get a Program from the model
                trace_log_lines("...")
                step_object = self._backend.step(act, program_result.call_results, self._tool_map)
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

        return act.result

    def wait_for_page_to_settle(self) -> None:
        self._actuator.wait_for_page_to_settle()

    def go_to_url(self, url: str) -> None:
        self._actuator.go_to_url(url)
        self.wait_for_page_to_settle()

    def cancel_prompt(self, act: Act | None = None) -> None:
        self._canceled = True
