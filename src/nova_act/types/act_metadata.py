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
import os
import re
from datetime import datetime
from typing import Dict

_FILENAME_SUB_RE = re.compile(r'[<>:"/\\|?*\x00-\x1F\s]')


def _safe_filename(s: str, max_length: int) -> str:
    """Replace invalid filename characters and whitespace with underscores."""
    safe = _FILENAME_SUB_RE.sub("_", s)
    safe = safe.strip("_")
    return safe[:max_length]


def build_trajectory_file_path(session_logs_directory: str, act_id: str, prompt: str) -> str:
    """Build the trajectory file path for an act.

    Args:
        session_logs_directory: The directory where session logs are stored.
        act_id: The act identifier.
        prompt: The act prompt text.

    Returns:
        The full file path for the trajectory JSON file.
    """
    prompt_filename_snippet = _safe_filename(prompt, 30)
    file_name_prefix = f"act_{act_id}_{prompt_filename_snippet}"
    trajectory_file_name = f"{file_name_prefix}_trajectory.json"
    return os.path.join(session_logs_directory, trajectory_file_name)


@dataclasses.dataclass(frozen=True)
class ActMetadata:
    session_id: str
    act_id: str
    num_steps_executed: int
    start_time: float | None
    end_time: float | None
    prompt: str
    step_server_times_s: list[float] = dataclasses.field(default_factory=list)
    time_worked_s: float | None = None
    human_wait_time_s: float = 0.0
    trajectory_file_path: str | None = None

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

        time_worked_line = ""
        if self.time_worked_s is not None:
            try:
                time_worked_str = _format_duration(self.time_worked_s)
                if self.human_wait_time_s > 0:
                    human_wait_str = _format_duration(self.human_wait_time_s)
                    time_worked_line = (
                        f"    time_worked = {time_worked_str} " f"(excluding {human_wait_str} human wait)\n"
                    )
                else:
                    time_worked_line = f"    time_worked = {time_worked_str}\n"
            except (TypeError, AttributeError):
                # Handle cases where time values are mocks or invalid types
                time_worked_line = f"    time_worked = {self.time_worked_s}\n"

        return (
            f"ActMetadata(\n"
            f"    session_id = {self.session_id}\n"
            f"    act_id = {self.act_id}\n"
            f"    num_steps_executed = {self.num_steps_executed}\n"
            f"    start_time = {start_time_str}\n"
            f"    end_time = {end_time_str}\n"
            f"{step_times_line}"
            f"{time_worked_line}"
            f"    prompt = '{self.prompt}'\n"
            f")"
        )


def _format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string.

    Examples:
        45.234 -> "45.2s"
        154.567 -> "2m 34.6s"
        3725.123 -> "1h 2m 5.1s"

    Args:
        seconds: Duration in seconds

    Returns:
        Human-readable duration string
    """
    if seconds < 60:
        return f"{seconds:.1f}s"

    # Use divmod for efficient calculation using division and modulo
    total_minutes, remaining_seconds = divmod(seconds, 60)
    total_minutes = int(total_minutes)

    if total_minutes < 60:
        return f"{total_minutes}m {remaining_seconds:.1f}s"

    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}h {minutes}m {remaining_seconds:.1f}s"
