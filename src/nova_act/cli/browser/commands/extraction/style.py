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
"""Style command for browser CLI."""

from __future__ import annotations

import json
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

STYLE_OUTPUT = OutputPathConfig("style", "json")


@click.command(name="style")
@click.argument("selector")
@click.argument("properties", nargs=-1)
@click.option("--output", "-o", help="Output file path (auto-generated if not specified)")
@click.option("--starting-page", help="Starting URL for new sessions (default: about:blank)")
@click.option("--timeout", type=int, help="Timeout in seconds")
@browser_command_options
@handle_common_errors
@pack_command_params
def style(
    selector: str,
    properties: tuple[str, ...],
    output: str | None,
    starting_page: str | None,
    timeout: int | None,
    params: CommandParams,
) -> None:
    """Get computed CSS styles for elements matching a selector.

    If PROPERTIES are specified, returns only those CSS properties.
    Otherwise returns all computed styles.

    Examples:
        act browser style "div.header"
        act browser style "div.header" color font-size
        act browser style "a[href]" color --json
        act browser style "button" --session-id my-session
        act browser style "div.header" --output styles.json
    """
    prep = prepare_session(params, starting_page)

    with command_session(
        "style", prep.manager, prep.session_info, params, log_args={"selector": selector, "output": output}
    ) as nova_act:
        output = resolve_output_path(output, STYLE_OUTPUT.filename, STYLE_OUTPUT.ext)
        with temporary_timeout(nova_act, timeout):
            actions = BrowserActions(nova_act)
            try:
                styles = actions.get_styles(selector, properties)
            except ValueError as exc:
                raise click.ClickException(str(exc)) from exc

            file_size = write_output_file(output, json.dumps(styles, indent=2))

        details = _build_details(params.session_id, selector, len(styles), output, file_size)
        echo_success(
            f"Computed styles for {len(styles)} element(s) matching '{selector}'",
            details=details,
        )


def _build_details(
    session_id: str,
    selector: str,
    count: int,
    file_path: str,
    file_size: int,
) -> dict[str, object]:
    """Build details dict for echo_success output."""
    details: dict[str, object] = {
        "count": count,
        "file": file_path,
    }
    if file_size < 4096:
        details["content"] = Path(file_path).read_text()
        details["content_truncated"] = False
    return details
