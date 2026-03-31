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
"""Process utilities for Nova Act CLI."""

import psutil


def is_process_running(pid: int | None) -> bool:
    """Check if a process with given PID is still running.

    Args:
        pid: Process ID to check

    Returns:
        True if process is running, False otherwise
    """
    if pid is None:
        return False

    return psutil.pid_exists(pid)
