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
import time
import uuid

# using dataclasses for end states
from dataclasses import dataclass
from typing import Dict

# using attrs to finely control mutability of types
from attrs import define, field
from attrs.setters import frozen

from nova_act.types.act_metadata import ActMetadata
from nova_act.types.api.step import ProgramErrorResponse
from nova_act.types.state.step import Step

DEFAULT_ACT_MAX_STEPS = 30


def _convert_max_steps(x: int | None) -> int:
    return x if x is not None else DEFAULT_ACT_MAX_STEPS


@dataclass
class ActSucceeded:
    response: str | None


@dataclass
class ActCanceled:
    pass


@dataclass
class ActFailed:
    response: ProgramErrorResponse


@define
class Act:
    # Required constructor params (immutable)
    prompt: str = field(on_setattr=frozen)
    session_id: str = field(on_setattr=frozen)
    endpoint_name: str | None = field(on_setattr=frozen)
    timeout: float = field(on_setattr=frozen)

    # Optional constructor params (immutable)
    max_steps: int = field(
        default=DEFAULT_ACT_MAX_STEPS,
        converter=_convert_max_steps,
        on_setattr=frozen,
    )
    model_temperature: int | None = field(default=None, on_setattr=frozen)
    model_top_k: int | None = field(default=None, on_setattr=frozen)
    model_seed: int | None = field(default=None, on_setattr=frozen)
    observation_delay_ms: int | None = field(default=None, on_setattr=frozen)

    # generate act_id and start_time on construction; make immutable
    id: str = field(factory=lambda: str(uuid.uuid4()), on_setattr=frozen, init=False)
    start_time: float = field(factory=lambda: time.time(), on_setattr=frozen, init=False)

    # rest of fields are mutable
    end_time: float | None = field(factory=lambda: None, init=False)
    _steps: list[Step] = field(factory=list, init=False)
    _result: ActSucceeded | ActCanceled | ActFailed | None = field(factory=lambda: None, init=False)

    acknowledged: bool = field(factory=lambda: False, init=False)
    is_complete: bool = field(factory=lambda: False, init=False)
    did_timeout: bool = field(factory=lambda: False, init=False)

    @property
    def steps(self) -> list[Step]:
        return self._steps.copy()  # Return a copy to prevent direct modification

    @property
    def metadata(self) -> ActMetadata:
        return ActMetadata(
            session_id=self.session_id,
            act_id=self.id,
            num_steps_executed=len(self._steps),
            start_time=self.start_time,
            end_time=self.end_time,
            step_server_times_s=self.get_step_server_times_s,
            prompt=self.prompt,
        )

    @property
    def get_step_server_times_s(self) -> list[float]:
        return [round(step.server_time_s, 3) for step in self._steps if step.server_time_s is not None]

    @property
    def result(self) -> ActSucceeded | ActCanceled | ActFailed | None:
        return self._result

    def add_step(self, step: Step) -> None:
        if self.is_complete:
            raise ValueError("Cannot add steps to a completed Act")
        self._steps.append(step)

    def complete(self, response: str | None) -> None:
        self.end_time = time.time()
        self._result = ActSucceeded(response)
        self.is_complete = True

    def cancel(self) -> None:
        self.end_time = time.time()
        self._result = ActCanceled()
        self.is_complete = True

    def fail(self, error_message: ProgramErrorResponse) -> None:
        self.end_time = time.time()
        self._result = ActFailed(error_message)
        self.is_complete = True
