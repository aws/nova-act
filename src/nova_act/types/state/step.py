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
from dataclasses import dataclass
from datetime import datetime as dt

from nova_act.types.api.step import StepObject


@dataclass(frozen=True)
class ModelInput:
    image: str
    prompt: str
    active_url: str


@dataclass(frozen=True)
class ModelOutput:
    awl_raw_program: str
    request_id: str


@dataclass(frozen=True)
class Step:
    model_input: ModelInput
    model_output: ModelOutput
    observed_time: dt
    rawMessage: StepObject
    server_time_s: float | None

    @classmethod
    def from_message(cls, message: StepObject) -> "Step":
        # Extract input data
        input_data = message.get("input", {})
        model_input = ModelInput(
            image=input_data.get("screenshot", ""),
            prompt=input_data.get("prompt", ""),
            active_url=input_data.get("metadata", {}).get("activeURL", ""),
        )

        # Extract output data
        output_data = message.get("output", {})
        model_output = ModelOutput(
            awl_raw_program=output_data.get("rawProgramBody", ""), request_id=output_data.get("requestId", "")
        )

        # Extract timing data
        observed_time = dt.fromtimestamp(time.time())
        server_time_value = message.get("server_time_s")
        server_time_s = float(server_time_value) if server_time_value is not None else None

        return cls(
            model_input=model_input,
            model_output=model_output,
            observed_time=observed_time,
            rawMessage=message,
            server_time_s=server_time_s,
        )

    # Input validation
    def __post_init__(self) -> None:
        """Validate instance after creation."""
        if not self.model_input.image:
            raise ValueError("Screenshot is required")
        if not self.model_output.awl_raw_program:
            raise ValueError("Program body is required")
