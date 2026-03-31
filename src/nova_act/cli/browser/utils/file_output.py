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
"""Shared file output utilities for CLI commands."""

import errno
import json
import pathlib
from typing import NamedTuple

from nova_act.cli.browser.utils.log_capture import get_current_command_dir
from nova_act.cli.core.json_output import ErrorCode
from nova_act.cli.core.output import exit_with_error


class OutputPathConfig(NamedTuple):
    """Configuration for auto-generated output file paths."""

    filename: str
    ext: str


def resolve_output_path(output: str | None, filename: str, ext: str) -> str:
    """Validate user-provided output path or auto-generate one inside the command subdir."""
    if output:
        validate_output_dir(output)
        return output
    return generate_output_path(filename, ext)


def generate_output_path(filename: str, ext: str) -> str:
    """Generate output path inside the current per-command subdirectory."""
    cmd_dir = get_current_command_dir()
    if cmd_dir is None:
        raise RuntimeError("generate_output_path called outside capture_command_log context")
    cmd_dir.mkdir(parents=True, exist_ok=True)
    return str(cmd_dir / f"{filename}.{ext}")


def write_output_file(path: str, content: str | bytes) -> int:
    """Write content to file, returning bytes written. Exits on error."""
    try:
        p = pathlib.Path(path)
        if isinstance(content, bytes):
            p.write_bytes(content)
            return len(content)
        p.write_text(content, encoding="utf-8")
        return len(content.encode("utf-8"))
    except OSError as e:
        msg = "Not enough disk space" if e.errno == errno.ENOSPC else str(e)
        exit_with_error(
            "File write error",
            msg,
            suggestions=["Check file permissions", "Verify output path exists"],
            error_code=ErrorCode.FILE_ERROR,
        )
        return 0  # unreachable


def validate_output_dir(path: str) -> None:
    """Exit with error if the parent directory of path doesn't exist."""
    parent = pathlib.Path(path).parent
    if not parent.exists():
        exit_with_error(
            "Invalid output path",
            f"Directory does not exist: {parent}",
            suggestions=["Create the directory first", "Use a different output path"],
            error_code=ErrorCode.FILE_ERROR,
        )


def format_result(result: object, output_format: str) -> str:
    """Format a result based on output format."""
    if output_format == "json":
        if isinstance(result, dict):
            return json.dumps(result, indent=2)
        else:
            # Wrap string result in JSON object
            return json.dumps({"result": result}, indent=2)
    else:
        if isinstance(result, (dict, list)):
            return json.dumps(result, indent=2, default=str)
        return str(result)
