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

import json
from dataclasses import dataclass, fields
from datetime import datetime

from nova_act.impl.program.base import Program
from nova_act.types.api.step import Statement
from nova_act.types.api.trace import TraceDict


@dataclass(frozen=True)
class ModelInput:
    image: str
    prompt: str
    active_url: str
    simplified_dom: str


@dataclass(frozen=True)
class ModelOutput:
    awl_raw_program: str
    request_id: str
    program_ast: list[Statement]

    @classmethod
    def from_plan_response(cls, plan_response: str, request_id: str = "") -> ModelOutput:
        """Instantiate from a plan response."""

        try:
            plan_response_json = json.loads(plan_response)
        except json.JSONDecodeError:
            raise ValueError("actuationPlanResponse is not JSON-Type.")

        if "rawProgramBody" not in plan_response_json:
            raise ValueError("actuationPlanResponse is missing rawProgramBody.")

        awl_raw_program = plan_response_json["rawProgramBody"]

        try:
            program_ast: list[Statement] = plan_response_json["program"]["body"][0]["body"]["body"]
        except (IndexError, KeyError, TypeError):
            raise LookupError("actuationPlanResponse is missing program body.")

        return cls(awl_raw_program=awl_raw_program, request_id=request_id, program_ast=program_ast)


@dataclass(frozen=True)
class Step:
    model_input: ModelInput
    model_output: ModelOutput
    observed_time: datetime
    server_time_s: float | None
    step_id: str | None = None
    trace: TraceDict | None = None

    # Input validation
    def __post_init__(self) -> None:
        """Validate instance after creation."""
        if not self.model_input.image:
            raise ValueError("Screenshot is required")
        if not self.model_output.awl_raw_program:
            raise ValueError("Program body is required")

    def with_program(self, program: Program) -> StepWithProgram:
        """Create a new instance with an interpreted Program."""
        return StepWithProgram(
            program=program,
            **{field.name: getattr(self, field.name) for field in fields(self)},
        )


@dataclass(frozen=True, kw_only=True)
class StepWithProgram(Step):
    program: Program
