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
"""Utility for tracking human wait time during act execution."""

import time


class HumanWaitTimeTracker:
    """Tracks cumulative human wait time during an act execution.

    This tracker is used to measure the total time spent waiting for human input
    (e.g., approve() or ui_takeover() calls) so that it can be excluded from the
    agent's "time worked" calculation.
    """

    def __init__(self) -> None:
        """Initialize a new HumanWaitTimeTracker."""
        self._total_wait_time_s: float = 0.0
        self._current_wait_start: float | None = None

    def start_wait(self) -> None:
        """Mark the start of a human wait period.

        Raises:
            RuntimeError: If a wait is already in progress (nested wait calls).
        """
        if self._current_wait_start is not None:
            raise RuntimeError("Wait already in progress")
        self._current_wait_start = time.time()

    def end_wait(self) -> None:
        """Mark the end of a human wait period and accumulate the duration.

        Raises:
            RuntimeError: If no wait is in progress.
        """
        if self._current_wait_start is None:
            raise RuntimeError("No wait in progress")
        duration = time.time() - self._current_wait_start
        self._total_wait_time_s += duration
        self._current_wait_start = None

    def get_total_wait_time_s(self) -> float:
        """Get the total accumulated wait time in seconds.

        Returns:
            The total wait time in seconds across all wait periods.
        """
        return self._total_wait_time_s

    def reset(self) -> None:
        """Reset the tracker for a new act.

        This clears both the total accumulated wait time and any in-progress wait.
        """
        self._total_wait_time_s = 0.0
        self._current_wait_start = None
