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
import json
import time
from typing import Callable

from nova_act.impl.controller import ControlState, NovaStateController
from nova_act.impl.interpreter import NovaActInterpreter
from nova_act.impl.program import format_return_value
from nova_act.impl.routes.base import Routes
from nova_act.tools.actuator.interface.actuator import ActuatorBase
from nova_act.tools.browser.interface.browser import (
    BrowserActuatorBase,
    BrowserObservation,
)
from nova_act.tools.browser.interface.types.agent_redirect_error import (
    AgentRedirectError,
)


from nova_act.types.act_errors import (
    ActAgentFailed,
    ActBadResponseError,
    ActCanceledError,
    ActError,
    ActExceededMaxStepsError,
    ActExecutionError,
    ActInvalidModelGenerationError,
    ActTimeoutError,
)
from nova_act.types.act_result import ActResult
from nova_act.types.errors import ClientNotStarted, InterpreterError, ValidationFailed
from nova_act.types.events import EventType, LogType
from nova_act.types.state.act import Act
from nova_act.util.decode_string import decode_string
from nova_act.util.event_handler import EventHandler
from nova_act.util.logging import (
    get_session_id_prefix,
    make_trace_logger,
)

_TRACE_LOGGER = make_trace_logger()

DEFAULT_ENDPOINT_NAME = "alpha-sunshine"


def _log_program(program: str) -> None:
    """Log a program to the terminal."""
    lines = program.split("\n")
    for line in lines:
        _TRACE_LOGGER.info(f"{get_session_id_prefix()}{line}")


def _handle_act_fail(f: Callable[[ActDispatcher, Act], ActResult]) -> Callable[[ActDispatcher, Act], ActResult]:
    """Update Act objects with appropriate metadata on Exceptions."""

    @functools.wraps(f)
    def wrapper(self: ActDispatcher, act: Act) -> ActResult:
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
        routes: Routes,
        controller: NovaStateController,
        event_handler: EventHandler,
    ):
        if not isinstance(actuator, BrowserActuatorBase):
            raise ValidationFailed("actuator must be an instance of BrowserActuatorBase")
        self._actuator = actuator
        self._routes = routes
        self._interpreter = NovaActInterpreter()

        self._tools = actuator.list_actions()
        self._tool_map = {tool.tool_name: tool for tool in self._tools}

        self._canceled = False
        self._event_handler = event_handler
        self._controller = controller

    def _cancel_act(self, act: Act) -> None:
        _TRACE_LOGGER.info(f"\n{get_session_id_prefix()}Terminating agent workflow")
        self._event_handler.send_event(
            type=EventType.LOG,
            log_level=LogType.INFO,
            data="Terminating agent workflow",
        )
        raise ActCanceledError()

    @_handle_act_fail
    def dispatch(self, act: Act) -> ActResult:
        """Dispatch an Act with given Backend and Actuator."""

        if self._routes is None or self._interpreter is None:
            raise ClientNotStarted("Run start() to start the client before accessing the Playwright Page.")


        error_executing_previous_step = None

        with self._controller as control:
            end_time = time.time() + act.timeout
            for i in range(1, act.max_steps + 1):
                if time.time() > end_time:
                    act.did_timeout = True
                    raise ActTimeoutError()

                if control.state == ControlState.CANCELLED:
                    self._cancel_act(act)

                if act.observation_delay_ms:
                    _TRACE_LOGGER.info(f"{get_session_id_prefix()}Observation delay: {act.observation_delay_ms}ms")
                    self._event_handler.send_event(
                        type=EventType.ACTION,
                        action="wait",
                        data=f"Observation delay: {act.observation_delay_ms}ms",
                    )
                    self._actuator.wait(act.observation_delay_ms / 1000)

                self._actuator.wait_for_page_to_settle()

                observation: BrowserObservation = self._actuator.take_observation()
                self._event_handler.send_event(type=EventType.ACTION, action="observation", data=observation)
                paused = False

                while control.state == ControlState.PAUSED:
                    paused = True
                    time.sleep(0.1)

                if control.state == ControlState.CANCELLED:
                    self._cancel_act(act)

                # Take another observation if we were paused
                if paused:
                    observation = self._actuator.take_observation()
                    self._event_handler.send_event(type=EventType.ACTION, action="observation", data=observation)

                _TRACE_LOGGER.info(f"{get_session_id_prefix()}...")
                step_object = self._routes.step(act, observation, error_executing_previous_step)
                raw_program_body = step_object.model_output.awl_raw_program
                if isinstance(raw_program_body, str):
                    lines = raw_program_body.split("\\n")
                    decoded_lines = []
                    for line in lines:
                        decoded_lines.append(decode_string(line))
                    raw_program_body = "\n".join(decoded_lines)
                _log_program(raw_program_body)
                act.add_step(step_object)

                error_executing_previous_step = None

                try:
                    program = self._interpreter.interpret_ast(step_object.model_output.program_ast)
                    program.compile(self._tool_map)
                    program_result = program.run(self._event_handler)

                    if throw_result := program_result.has_throw():
                        message = format_return_value(throw_result.return_value)
                        raise ActAgentFailed(message=message)
                    elif exception_result := program_result.has_exception():
                        assert exception_result.error is not None
                        raise exception_result.error

                except AgentRedirectError as e:
                    # Client wants to redirect the agent to try a different action
                    error_executing_previous_step = e
                    _log_program("AgentRedirect: " + e.error_and_correction)
                except ValueError as e:
                    # Interpreter received invalid Statements from server
                    raise ActBadResponseError(
                        request_id=step_object.model_output.request_id,
                        status_code=200,
                        message=str(e),
                        raw_response=json.dumps(step_object.model_output.program_ast),
                    )
                except InterpreterError as e:
                    # Interpreter received invalid action type or arguments from model
                    raise ActInvalidModelGenerationError(
                        request_id=step_object.model_output.request_id,
                        status_code=200,
                        message=str(e),
                        raw_response=step_object.model_output.awl_raw_program,
                    )
                else:
                    if return_result := program_result.has_return():
                        result = return_result.return_value
                        act.complete(str(result) if result is not None else None)
                        break

            if not act.is_complete:
                raise ActExceededMaxStepsError(f"Exceeded max steps {act.max_steps} without return.")

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
