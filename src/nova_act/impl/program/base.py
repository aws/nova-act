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
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict

from nova_act.tools.actuator.interface.actuator import ActionType
from nova_act.tools.compatibility import callable_tool
from nova_act.types.act_errors import ActToolError
from nova_act.types.json_type import JSONType


class FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class Call(FrozenBaseModel):
    name: str
    kwargs: dict[str, JSONType]
    id: str
    is_tool: bool = False


@dataclass(frozen=True)
class CompiledCall:
    source: Call
    target: ActionType


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

    def has_observation(self) -> CallResult | None:
        return next((r for r in self.call_results if r.call.name == "takeObservation"), None)


@dataclass(frozen=True)
class CompiledProgram:
    calls: list[CompiledCall]


class Program(FrozenBaseModel):
    calls: list[Call]

    def compile(self, tool_map: dict[str, ActionType]) -> CompiledProgram:
        compiled_calls = []
        for call in self.calls:
            target = tool_map.get(call.name)
            if target is None:
                raise ActToolError(message=f"Tool '{call.name}' was not found.")
            compiled_calls.append(CompiledCall(source=call, target=callable_tool(target)))
        return CompiledProgram(calls=compiled_calls)
