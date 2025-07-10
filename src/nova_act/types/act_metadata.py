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
from datetime import datetime
from typing import Dict


@dataclasses.dataclass(frozen=True)
class ActMetadata:
    session_id: str
    act_id: str
    num_steps_executed: int
    start_time: float | None
    end_time: float | None
    prompt: str
    step_server_times_s: list[float] = dataclasses.field(default_factory=list)

    def __repr__(self) -> str:
        local_tz = datetime.now().astimezone().tzinfo

        # Convert Unix timestamps to readable format if they exist
        start_time_str = (
            datetime.fromtimestamp(self.start_time, tz=local_tz).strftime("%Y-%m-%d %H:%M:%S.%f %Z")
            if self.start_time is not None
            else "None"
        )
        end_time_str = (
            datetime.fromtimestamp(self.end_time, tz=local_tz).strftime("%Y-%m-%d %H:%M:%S.%f %Z")
            if self.end_time is not None
            else "None"
        )

        step_times_line = ""
        if self.step_server_times_s and any(t != 0 for t in self.step_server_times_s):
            formatted_times = [f"{t:.3f}" for t in self.step_server_times_s]
            step_times_line = f"    step_server_times_s = {formatted_times}\n"

        return (
            f"ActMetadata(\n"
            f"    session_id = {self.session_id}\n"
            f"    act_id = {self.act_id}\n"
            f"    num_steps_executed = {self.num_steps_executed}\n"
            f"    start_time = {start_time_str}\n"
            f"    end_time = {end_time_str}\n"
            f"{step_times_line}"
            f"    prompt = '{self.prompt}'\n"
            f")"
        )
