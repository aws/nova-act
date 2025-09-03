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
import codecs
import time

from boto3.session import Session
from requests import Response
from strands.tools.decorator import DecoratedFunctionTool
from typing_extensions import Any, Callable, Dict, Set

from nova_act.impl.actuation.interface.actuator import ActuatorBase
from nova_act.impl.actuation.interface.browser import (
    BrowserActuatorBase,
    BrowserObservation,
)
from nova_act.impl.actuation.interface.types.agent_redirect_error import (
    AgentRedirectError,
)
from nova_act.impl.actuation.routing.error_handler import handle_error
from nova_act.impl.actuation.routing.interpreter import NovaActInterpreter
from nova_act.impl.actuation.routing.request import construct_plan_request
from nova_act.impl.actuation.routing.routes import Routes
from nova_act.impl.backend import BackendInfo
from nova_act.impl.controller import ControlState, NovaStateController
from nova_act.impl.protocol import NovaActClientErrors
from nova_act.types.act_errors import ActError
from nova_act.types.act_result import ActResult
from nova_act.types.api.step import ProgramErrorResponse
from nova_act.types.errors import ClientNotStarted, InterpreterError, ValidationFailed
from nova_act.types.events import EventType, LogType
from nova_act.types.state.act import Act
from nova_act.types.state.step import Step
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
    _TRACE_LOGGER.info(f"{get_session_id_prefix()}{lines[0]}")
    for line in lines[1:]:
        _TRACE_LOGGER.info(f">> {line}")


class ActDispatcher:
    _actuator: BrowserActuatorBase

    def __init__(
        self,
        backend_info: BackendInfo,
        event_handler: EventHandler,
        controller: NovaStateController,
        nova_act_api_key: str | None,
        actuator: ActuatorBase | None,
        tty: bool,
        boto_session: Session | None = None,
    ):
        self._nova_act_api_key = nova_act_api_key
        self._backend_info = backend_info
        self._tty = tty
        self._boto_session = boto_session
        if not isinstance(actuator, BrowserActuatorBase):
            raise ValidationFailed("actuator must be an instance of BrowserActuatorBase")
        self._actuator = actuator
        self._routes = Routes(
            self._backend_info,
            self._nova_act_api_key,
            boto_session=boto_session,
        )
        self._interpreter = NovaActInterpreter(actuator=self._actuator, event_handler=event_handler)


        self._canceled = False
        self._event_handler = event_handler
        self._controller = controller

    def dispatch(self, act: Act) -> ActResult | ActError:
        """Dispatch an Act with given Backend and Actuator."""

        if self._routes is None or self._interpreter is None:
            raise ClientNotStarted("Run start() to start the client before accessing the Playwright Page.")

        if not isinstance(self._actuator, BrowserActuatorBase):
            raise ValidationFailed("actuator must be an instance of BrowserActuatorBase")

        endpoint_name = act.endpoint_name

        error_executing_previous_step = None

        with self._controller as control:
            end_time = time.time() + act.timeout
            for i in range(1, act.max_steps + 1):
                if time.time() > end_time:
                    act.did_timeout = True
                    error = ProgramErrorResponse(type="NovaActClient", error="Act timed out")
                    act.fail(error)
                    break

                if control.state == ControlState.CANCELLED:
                    _TRACE_LOGGER.info(f"\n{get_session_id_prefix()}Terminating agent workflow")
                    self._event_handler.send_event(
                        type=EventType.LOG,
                        log_level=LogType.INFO,
                        data="Terminating agent workflow",
                    )
                    act.cancel()
                    break

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

                # NOTE: we ignore typing on the following statement due to the following mypy bug:
                # https://github.com/python/mypy/issues/10910
                if control.state == ControlState.CANCELLED:  # type: ignore
                    _TRACE_LOGGER.info(f"\n{get_session_id_prefix()}Terminating agent workflow")
                    self._event_handler.send_event(
                        type=EventType.LOG,
                        log_level=LogType.INFO,
                        data="Terminating agent workflow",
                    )
                    act.cancel()
                    break

                # Take another observation if we were paused
                if paused:
                    observation = self._actuator.take_observation()
                    self._event_handler.send_event(type=EventType.ACTION, action="observation", data=observation)

                plan_request = construct_plan_request(
                    act_id=act.id,
                    observation=observation,
                    prompt=act.prompt,
                    error_executing_previous_step=error_executing_previous_step,
                    is_initial_step=i == 1,
                    endpoint_name=endpoint_name,
                )

                _TRACE_LOGGER.info("...")
                step_response = self._routes.step(
                    plan_request=plan_request,
                    act=act,
                    session_id=act.session_id,
                    metadata=act.metadata,
                )

                if "error" in step_response:
                    act.fail(step_response["error"])
                    break

                statements = step_response["program_statements"]
                raw_program_body = step_response["raw_program_body"]
                step_object = step_response["step_object"]

                if isinstance(raw_program_body, str):
                    raw_program_body = codecs.decode(raw_program_body, "unicode_escape")

                _log_program(raw_program_body)
                act.add_step(Step.from_message(step_object))
                error_executing_previous_step = None

                try:
                    interpreted_ast = self._interpreter.interpret_ast(statements)
                    is_act_done = interpreted_ast["is_act_done"]


                    if "program_error" in interpreted_ast:
                        act.fail(interpreted_ast["program_error"])
                        break
                    if is_act_done:
                        result = interpreted_ast["result"]
                        act.complete(str(result) if result is not None else None)
                        break
                except AgentRedirectError as e:
                    is_act_done = False
                    error_executing_previous_step = e
                except InterpreterError as e:
                    act.fail(
                        ProgramErrorResponse(
                            type="NovaActClient",
                            code=NovaActClientErrors.INTERPRETATION_ERROR.value,
                            message=str(e),
                        )
                    )
                    break

            if not act.is_complete:
                act.fail(
                    ProgramErrorResponse(
                        type="NovaActClient",
                        code="MAX_STEPS_EXCEEDED",
                    )
                )
        act_result = handle_error(act, self._backend_info)
        self._event_handler.send_event(
            type=EventType.ACTION,
            action="result",
            data=act_result,
        )
        return act_result

    def wait_for_page_to_settle(self) -> None:
        self._actuator.wait_for_page_to_settle()

    def go_to_url(self, url: str) -> None:
        self._actuator.go_to_url(url)
        self.wait_for_page_to_settle()

    def cancel_prompt(self, act: Act | None = None) -> None:
        self._canceled = True
