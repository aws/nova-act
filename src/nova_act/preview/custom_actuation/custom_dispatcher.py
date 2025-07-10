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
from contextlib import nullcontext
from datetime import datetime, timezone
from typing import ContextManager

from nova_act.impl.backend import BackendInfo
from nova_act.impl.dispatcher import ActDispatcher
from nova_act.impl.keyboard_event_watcher import KeyboardEventWatcher
from nova_act.preview.custom_actuation.interface.actuator import ActuatorBase
from nova_act.preview.custom_actuation.interface.browser import BrowserActuatorBase, BrowserObservation
from nova_act.preview.custom_actuation.interface.types.agent_redirect_error import AgentRedirectError
from nova_act.preview.custom_actuation.routing.error_handler import handle_error
from nova_act.preview.custom_actuation.routing.interpreter import AWLInterpreter
from nova_act.preview.custom_actuation.routing.request import (
    construct_plan_request,
)
from nova_act.preview.custom_actuation.routing.routes import Routes
from nova_act.types.act_errors import ActError
from nova_act.types.act_result import ActResult
from nova_act.types.errors import ClientNotStarted, ValidationFailed
from nova_act.types.state.act import Act
from nova_act.types.state.step import Step
from nova_act.util.logging import get_session_id_prefix, make_trace_logger

_TRACE_LOGGER = make_trace_logger()


def _log_program(program: str | None):
    """Log a program to the terminal."""
    if not program:
        return
    lines = program.split("\n")
    _TRACE_LOGGER.info(f"{get_session_id_prefix()}{lines[0]}")
    for line in lines[1:]:
        _TRACE_LOGGER.info(f">> {line}")


class CustomActDispatcher(ActDispatcher):
    _actuator: ActuatorBase

    def __init__(
        self,
        backend_info: BackendInfo,
        nova_act_api_key: str | None,
        actuator: ActuatorBase | None,
        tty: bool,
    ):
        self._nova_act_api_key = nova_act_api_key
        self._backend_info = backend_info
        self._tty = tty
        if not isinstance(actuator, BrowserActuatorBase):
            raise ValidationFailed("actuator must be an instance of BrowserActuatorBase")
        self._actuator = actuator
        self._routes = Routes(
            self._backend_info,
            self._nova_act_api_key,
        )
        self._interpreter = AWLInterpreter(actuator=self._actuator)

    def dispatch_and_wait_for_prompt_completion(self, act: Act) -> ActResult | ActError:
        """Act using custom actuation"""

        if self._routes is None or self._interpreter is None:
            raise ClientNotStarted("Run start() to start the client before accessing the Playwright Page.")

        if not isinstance(self._actuator, BrowserActuatorBase):
            raise ValidationFailed("actuator must be an instance of BrowserActuatorBase")

        kb_cm: KeyboardEventWatcher | ContextManager[None] = (
            KeyboardEventWatcher(chr(24), "ctrl+x", "stop agent act() call without quitting the browser")
            if self._tty
            else nullcontext()
        )


        error_executing_previous_step = None

        with kb_cm as watcher:
            end_time = time.time() + act.timeout
            for i in range(1, act.max_steps + 1):
                if time.time() > end_time:
                    act.did_timeout = True
                    error = {"type": "NovaActClient", "error": "Act timed out"}
                    act.fail(error)
                    break

                if self._tty:
                    assert watcher is not None
                    triggered = watcher.is_triggered()
                    if triggered:
                        _TRACE_LOGGER.info(f"\n{get_session_id_prefix()}Terminating agent workflow")
                        act.cancel()
                        break

                try:
                    self._actuator.wait_for_page_to_settle(
                        {
                            "max_timeout_ms": 180000,
                            "number_of_checks": 3,
                            "percent_difference_threshold": 25,
                            "polling_interval_ms": 500,
                            "start_time": datetime.now(timezone.utc),
                        }
                    )

                    observation: BrowserObservation = self._actuator.take_observation(
                        save_screenshot=False,
                    )

                    plan_request = construct_plan_request(
                        act_id=act.id,
                        observation=observation,
                        prompt=act.prompt,
                        error_executing_previous_step=error_executing_previous_step,
                        is_initial_step=i == 1,
                        endpoint_name=act.endpoint_name,
                    )

                    _TRACE_LOGGER.info("...")
                    program, step_object = self._routes.step(
                        plan_request=plan_request,
                        act=act,
                        session_id=act.session_id,
                        metadata=act.metadata,
                    )

                    # UTF-decode program
                    if isinstance(program, str):
                        program = codecs.decode(program, "unicode_escape")

                    _log_program(program)
                    if program is None:
                        error_message = step_object
                        act.fail(error_message)
                        break

                    act.add_step(Step.from_message(step_object))

                    error_executing_previous_step = None
                    try:
                        is_act_done, result, program_error = self._interpreter.interpret(program)
                        if program_error is not None:
                            error_dict = dict(program_error)
                            act.fail(error_dict)
                            break
                        elif is_act_done:
                            act.complete(str(result))
                            break
                    except AgentRedirectError as e:
                        is_act_done = False
                        error_executing_previous_step = e

                except Exception:
                    raise

            if not act.is_complete:
                error = {"type": "NovaActClient", "code": "MAX_STEPS_EXCEEDED"}
                act.fail(error)

        return handle_error(act, self._backend_info)

    def wait_for_page_to_settle(self, session_id: str, timeout: int | None = None) -> None:
        pass

    def go_to_url(self, url: str, session_id: str, timeout: int | None = None) -> None:
        pass

    def cancel_prompt(self, act: Act | None = None):
        pass
