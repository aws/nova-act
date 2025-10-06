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
from dataclasses import dataclass, field
from typing import Callable
from uuid import uuid4

from nova_act.tools.actuator.interface.actuator import ActionType
from nova_act.tools.browser.interface.types.agent_redirect_error import AgentRedirectError
from nova_act.types.act_errors import ActActuationError, ActError, ActToolError
from nova_act.types.errors import InterpreterError
from nova_act.types.events import EventType
from nova_act.types.json_type import JSONType
from nova_act.util.event_handler import EventHandler


@dataclass
class Call:  # type: ignore[explicit-any]
    name: str
    kwargs: dict[str, JSONType]
    id: str = field(default_factory=lambda: str(uuid4()))
    _callable: Callable[..., JSONType] | None = None  # type: ignore[explicit-any]


@dataclass(frozen=True)
class CallResult:
    call: Call
    return_value: JSONType
    error: Exception | None


@dataclass(frozen=True)
class ProgramResult:
    call_results: list[CallResult] = field(default_factory=list)

    def has_return(self) -> CallResult | None:
        return next((r for r in self.call_results if r.call.name == "return"), None)

    def has_throw(self) -> CallResult | None:
        return next((r for r in self.call_results if r.call.name == "throw"), None)

    def has_exception(self) -> CallResult | None:
        return next((r for r in self.call_results if r.error is not None), None)


@dataclass(frozen=True)
class Program:
    calls: list[Call]

    def compile(self, tool_map: dict[str, ActionType]) -> None:
        for call in self.calls:
            call._callable = tool_map.get(call.name)
            if call._callable is None:
                raise ActToolError(message=f"Tool '{call.name}' was not found.")

    def run(self, event_handler: EventHandler) -> ProgramResult:
        call_results: list[CallResult] = []

        for call in self.calls:
            return_value = None
            error: Exception | None = None

            try:
                if call._callable is None:
                    raise ActError(f"Expected tool '{call.name}' to be present.")

                return_value = call._callable(**call.kwargs)
                event_handler.send_event(type=EventType.ACTION, action=f"{call.name}({call.kwargs})", data=return_value)


            except (AgentRedirectError, InterpreterError) as e:
                error = e
            except Exception as e:
                event_handler.send_event(type=EventType.LOG, action=call.name, data=f"{type(e).__name__}: {e}")
                error = ActActuationError(message=f"{type(e).__name__}: {e}")

            call_result = CallResult(call=call, return_value=return_value, error=error)
            call_results.append(call_result)

            # Terminate program early
            if call.name in ["return", "throw"] or error is not None:
                break

        return ProgramResult(call_results=call_results)


def format_return_value(return_value: JSONType) -> str:
    if isinstance(return_value, str):
        return return_value
    else:
        try:
            return json.dumps(return_value, indent=2)
        except Exception:
            return str(return_value)
