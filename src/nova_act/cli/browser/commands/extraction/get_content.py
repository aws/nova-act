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
"""Get-content command for browser CLI."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click

from nova_act.cli.browser.services.browser_actions import BrowserActions
from nova_act.cli.browser.utils.decorators import (
    browser_command_options,
    pack_command_params,
)
from nova_act.cli.browser.utils.error_handlers import handle_common_errors
from nova_act.cli.browser.utils.file_output import (
    OutputPathConfig,
    resolve_output_path,
    write_output_file,
)
from nova_act.cli.browser.utils.session import command_session, prepare_session
from nova_act.cli.browser.utils.timeout import temporary_timeout
from nova_act.cli.core.output import echo_success

if TYPE_CHECKING:
    from nova_act.cli.browser.types import CommandParams

CONTENT_OUTPUT = OutputPathConfig("content", "txt")

FORMAT_EXTENSIONS = {"text": "txt", "html": "html", "markdown": "md"}


@click.command(name="get-content")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "html", "markdown"]),
    default="text",
    help="Output format (default: text)",
)
@click.option("--output", "-o", help="Output file path (auto-generated if not specified)")
@click.option("--timeout", type=int, help="Timeout in seconds")
@browser_command_options
@handle_common_errors
@pack_command_params
def get_content(
    output_format: str,
    output: str | None,
    timeout: int | None,
    params: CommandParams,
) -> None:
    """Get the text content of the current page.

    Examples:
        act browser get-content
        act browser get-content --session-id my-session
        act browser get-content --format html
        act browser get-content --format markdown --output page.md
    """
    prep = prepare_session(params, None)

    ext = FORMAT_EXTENSIONS[output_format]
    with command_session(
        "get_content", prep.manager, prep.session_info, params, log_args={"format": output_format, "output": output}
    ) as nova_act:
        output = resolve_output_path(output, CONTENT_OUTPUT.filename, ext)
        with temporary_timeout(nova_act, timeout):
            actions = BrowserActions(nova_act)
            content = actions.get_content(output_format)
            size = write_output_file(output, content)
            details: dict[str, object] = {
                "file": output,
                "size": size,
            }
            if size < 4096:
                details["content"] = Path(output).read_text()
                details["content_truncated"] = False
            echo_success(
                f"Content saved to {output}",
                details=details,
            )
