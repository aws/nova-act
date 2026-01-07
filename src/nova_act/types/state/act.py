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
import dataclasses
import time

# using dataclasses for end states
from typing import Dict

# using attrs to finely control mutability of types
from attrs import define, field
from attrs.setters import frozen

from nova_act.tools.actuator.interface.actuator import ActionType
from nova_act.types.act_metadata import ActMetadata
from nova_act.types.act_result import ActGetResult
from nova_act.types.state.step import StepWithProgram
from nova_act.types.workflow_run import WorkflowRun

DEFAULT_ACT_MAX_STEPS = 30


def _convert_max_steps(x: int | None) -> int:
    return x if x is not None else DEFAULT_ACT_MAX_STEPS


@define
class Act:
    # Required constructor params (immutable)
    id: str = field(on_setattr=frozen)
    prompt: str = field(on_setattr=frozen)
    session_id: str = field(on_setattr=frozen)
    timeout: float = field(on_setattr=frozen)

    # Optional constructor params (immutable)
    max_steps: int = field(
        default=DEFAULT_ACT_MAX_STEPS,
        converter=_convert_max_steps,
        on_setattr=frozen,
    )
    model_temperature: float | None = field(default=None, on_setattr=frozen)
    model_top_k: int | None = field(default=None, on_setattr=frozen)
    model_seed: int | None = field(default=None, on_setattr=frozen)
    observation_delay_ms: int | None = field(default=None, on_setattr=frozen)
    ignore_screen_dims_check: bool = field(default=False, on_setattr=frozen)


    tools: list[ActionType] = field(factory=list)  # HITL + custom tools
    # Workflow context (immutable)
    workflow_run: WorkflowRun | None = field(default=None, on_setattr=frozen)

    # generate start_time on construction; make immutable
    start_time: float = field(factory=lambda: time.time(), on_setattr=frozen, init=False)

    # rest of fields are mutable
    end_time: float | None = field(factory=lambda: None, init=False)
    _steps: list[StepWithProgram] = field(factory=list, init=False)
    _result: ActGetResult | None = field(factory=lambda: None, init=False)

    acknowledged: bool = field(factory=lambda: False, init=False)
    is_complete: bool = field(factory=lambda: False, init=False)
    did_timeout: bool = field(factory=lambda: False, init=False)

    @property
    def steps(self) -> list[StepWithProgram]:
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
    def result(self) -> ActGetResult | None:
        return self._result

    def add_step(self, step: StepWithProgram) -> None:
        if self.is_complete:
            raise ValueError("Cannot add steps to a completed Act")
        self._steps.append(step)

    def complete(self, response: str | None) -> None:
        self.end_time = time.time()
        # fmt: off
        self._result = ActGetResult(
            response=response,
            metadata=self.metadata,
        )
        # fmt: on
        self.is_complete = True

    def set_time_worked(self, time_worked_s: float | None, human_wait_time_s: float) -> None:
        """Set time worked metrics after act completion.

        This method updates the act's result metadata with time worked information.
        It should only be called after the act has completed and has a result.

        Args:
            time_worked_s: The calculated time worked in seconds (excluding human wait time)
            human_wait_time_s: The total human wait time in seconds

        Note:
            This method uses object.__setattr__() to update the frozen ActResult dataclass.
            This is intentional as time worked is calculated after the result is created.
        """
        if self._result is None:
            # Act has no result yet - this should not happen in normal flow
            return

        # Create new metadata with time worked fields using dataclasses.replace
        new_metadata = dataclasses.replace(
            self._result.metadata,
            time_worked_s=time_worked_s,
            human_wait_time_s=human_wait_time_s,
        )

        # Update the frozen ActResult with new metadata
        # Using object.__setattr__() is necessary because ActResult is a frozen dataclass
        object.__setattr__(self._result, "metadata", new_metadata)
