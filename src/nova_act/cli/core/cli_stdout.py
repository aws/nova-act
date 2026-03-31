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
"""CLI stdout management — shared by output.py and json_output.py to avoid circular imports."""

import sys
from contextvars import ContextVar
from typing import TextIO

# Original stdout — set by capture_command_log so CLI output bypasses the tee writer
_original_stdout: ContextVar[TextIO | None] = ContextVar("_original_stdout", default=None)


def get_cli_stdout() -> TextIO:
    """Get the original stdout for CLI output (bypasses capture_command_log tee)."""
    return _original_stdout.get() or sys.stdout


def set_original_stdout(stream: TextIO | None) -> None:
    """Set the original stdout (called by capture_command_log)."""
    _original_stdout.set(stream)
