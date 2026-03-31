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
"""Query command for browser CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import click

from nova_act.cli.browser.services.browser_actions import ALL_PROPERTIES, BrowserActions
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

QUERY_OUTPUT = OutputPathConfig("query", "json")


def _parse_properties(properties: str | None) -> tuple[str, ...]:
    """Parse and validate the --properties filter."""
    if not properties:
        return ALL_PROPERTIES
    requested = tuple(p.strip() for p in properties.split(","))
    invalid = [p for p in requested if p not in ALL_PROPERTIES]
    if invalid:
        raise click.BadParameter(f"Invalid properties: {', '.join(invalid)}. " f"Allowed: {', '.join(ALL_PROPERTIES)}")
    return requested


@click.command(name="query")
@click.argument("selector")
@click.option("--output", "-o", help="Output file path (auto-generated if not specified)")
@click.option("--properties", default=None, help="Comma-separated property filter (tag,text,visible,boundingBox)")
@click.option("--timeout", type=int, help="Timeout in seconds")
@click.option("--starting-page", help="Starting URL for new sessions (default: about:blank)")
@browser_command_options
@handle_common_errors
@pack_command_params
def query(
    selector: str,
    output: str | None,
    properties: str | None,
    timeout: int | None,
    starting_page: str | None,
    params: CommandParams,
) -> None:
    """Query page elements matching a CSS selector.

    Returns properties (tag, text, visible, boundingBox) for each matching element.

    Examples:
        act browser query "div.header"
        act browser query "a[href]" --properties tag,text
        act browser query "button" --json
        act browser query "input" --session-id my-session --timeout 10
        act browser query "h1" --output /tmp/headings.json
    """
    props = _parse_properties(properties)

    prep = prepare_session(params, starting_page)

    with command_session(
        "query",
        prep.manager,
        prep.session_info,
        params,
        log_args={"selector": selector, "properties": properties, "output": output},
    ) as nova_act:
        output = resolve_output_path(output, QUERY_OUTPUT.filename, QUERY_OUTPUT.ext)
        with temporary_timeout(nova_act, timeout):
            actions = BrowserActions(nova_act)
            elements = actions.query_dom(selector, props)
            content = json.dumps(elements, indent=2, default=str)
            file_size = write_output_file(output, content)
            details: dict[str, object] = {
                "file": output,
                "count": len(elements),
            }
            if file_size < 4096:
                details["content"] = Path(output).read_text()
                details["content_truncated"] = False
            echo_success(
                f"Found {len(elements)} element(s) matching '{selector}'",
                details=details,
            )
