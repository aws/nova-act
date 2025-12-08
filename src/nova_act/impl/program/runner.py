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
import json
import logging
from typing import Protocol, cast

from nova_act.impl.program.base import CallResult, CompiledProgram, ProgramResult
from nova_act.impl.thinker import get_current_thinker
from nova_act.tools.browser.interface.browser import BrowserObservation
from nova_act.tools.browser.interface.types.agent_redirect_error import AgentRedirectError
from nova_act.types.act_errors import (
    ActActuationError,
    ActAgentFailed,
    ActInvalidModelGenerationError,
    ActStateGuardrailError,
    ActToolError,
    NoHumanInputToolAvailable,
)
from nova_act.types.errors import InterpreterError
from nova_act.types.events import EventType
from nova_act.types.guardrail import GuardrailCallable, GuardrailDecision, GuardrailInputState
from nova_act.types.json_type import JSONType
from nova_act.util.event_handler import EventHandler
from nova_act.util.logging import SessionState, set_logging_session_state, trace_log_lines


def format_return_value(return_value: JSONType) -> str:
    if isinstance(return_value, str):
        return return_value
    else:
        try:
            return json.dumps(return_value, indent=2)
        except Exception:
            return str(return_value)


class SafeLogger(Protocol):
    """Custom Protocol to denote Callable[[str, int], None] without required second argument."""

    def __call__(self, message: str, level: int = logging.INFO) -> None: ...


def get_safe_log() -> SafeLogger:
    """Return a Thinker if we're in context, else trace_log_lines."""
    if (thinker := get_current_thinker()) is not None:
        return thinker.safe_log
    else:
        return trace_log_lines


class ProgramRunner:
    def __init__(
        self,
        event_handler: EventHandler,
        state_guardrail: GuardrailCallable | None = None,
        verbose: bool = False,
    ):
        self.event_handler = event_handler
        self.state_guardrail = state_guardrail
        self.verbose = verbose

    def run(self, program: CompiledProgram) -> ProgramResult:
        """Run a program."""
        safe_log = get_safe_log()
        call_results: list[CallResult] = []

        for call in program.calls:
            if self.verbose:
                safe_log(f"{call.source.name}({call.source.kwargs});")
            return_value = None
            error: Exception | None = None

            try:
                if call.source.name in ("waitForPageToSettle", "takeObservation"):
                    set_logging_session_state(SessionState.OBSERVING)
                else:
                    set_logging_session_state(SessionState.ACTING)

                return_value = call.target(**call.source.kwargs)

                # Check state guardrail if configured
                # Note that we also run the guardrail within url.py:validate_url()
                if self.state_guardrail is not None and call.source.name == "takeObservation":
                    observation = cast(BrowserObservation, return_value)
                    decision = self.state_guardrail(GuardrailInputState(browser_url=observation["activeURL"]))
                    if decision == GuardrailDecision.BLOCK:
                        safe_log("State guardrail denied action", logging.WARNING)
                        raise ActStateGuardrailError()

                # Log tool call result
                if call.source.is_tool:
                    safe_log(
                        f'Result for tool call "{call.source.name}" with call id "{call.source.id}": {return_value}'
                    )

                self.event_handler.send_event(
                    type=EventType.ACTION, action=f"{call.source.name}({call.source.kwargs})", data=return_value
                )

            except NoHumanInputToolAvailable as e:
                safe_log(f"Human takeover tool not implemented: {e}", logging.ERROR)
                error = ActAgentFailed(message="HumanValidationError")

            except (AgentRedirectError, ActStateGuardrailError) as e:
                error = e
            except InterpreterError as e:
                error = ActInvalidModelGenerationError(message=str(e), raw_response=str(e))
            except Exception as e:
                self.event_handler.send_event(
                    type=EventType.LOG, action=call.source.name, data=f"{type(e).__name__}: {e}"
                )
                error = ActActuationError(message=f"{type(e).__name__}: {e}")
                if isinstance(e, ValueError):
                    error = ActInvalidModelGenerationError(message=f"{type(e).__name__}: {e}")

                if call.source.is_tool:
                    error = ActToolError(message=f"{type(e).__name__}: {e}")

            call_result = CallResult(call=call.source, return_value=return_value, error=error)
            call_results.append(call_result)

            # Terminate program early
            if call.source.name in ["return", "throw"] or not isinstance(error, (AgentRedirectError, type(None))):
                break

        return ProgramResult(call_results=call_results)
