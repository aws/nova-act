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
"""Console-log command — display captured browser console messages."""

from __future__ import annotations

import json as _json
from typing import TYPE_CHECKING

import click

from nova_act.cli.browser.services.console_capture import (
    ConsoleCaptureService,
    ConsoleEntry,
)
from nova_act.cli.browser.utils.decorators import (
    browser_command_options,
    pack_command_params,
)
from nova_act.cli.browser.utils.error_handlers import handle_common_errors
from nova_act.cli.browser.utils.session import (
    command_session,
    get_active_page,
    prepare_session,
)
from nova_act.cli.core.json_output import is_json_mode
from nova_act.cli.core.output import echo_success, get_cli_stdout

if TYPE_CHECKING:
    from nova_act.cli.browser.types import CommandParams

# Module-level registry: session_id -> ConsoleCaptureService
_capture_registry: dict[str, ConsoleCaptureService] = {}


def get_or_create_capture(session_id: str) -> ConsoleCaptureService:
    """Get existing capture service or create a new one for the session."""
    if session_id not in _capture_registry:
        _capture_registry[session_id] = ConsoleCaptureService()
    return _capture_registry[session_id]


def _entry_to_dict(entry: ConsoleEntry) -> dict[str, object]:
    result: dict[str, object] = {
        "level": entry.level,
        "text": entry.text,
        "timestamp": entry.timestamp,
    }
    if entry.source_url:
        result["source_url"] = entry.source_url
    if entry.line_number is not None:
        result["line_number"] = entry.line_number
    if entry.column_number is not None:
        result["column_number"] = entry.column_number
    if entry.args:
        result["args"] = entry.args
    return result


def _format_entry_line(entry: ConsoleEntry) -> str:
    level = entry.level.upper()
    source = ""
    if entry.source_url:
        url = entry.source_url.rsplit("/", 1)[-1] if "/" in entry.source_url else entry.source_url
        if entry.line_number is not None:
            source = f"{url}:{entry.line_number}"
        else:
            source = url
    text = entry.text[:80] + "..." if len(entry.text) > 80 else entry.text
    return f"{level:<10} {text:<80} {source}"


@click.command("console-log")
@click.option("--level", default=None, help="Filter by level (log, warning, error, info, debug, pageerror)")
@click.option("--filter", "text_filter", default=None, help="Glob pattern to filter message text")
@click.option("--limit", default=50, type=int, help="Max entries to display (default: 50)")
@click.option("--clear", is_flag=True, help="Clear captured entries")
@click.option("--errors-only", is_flag=True, help="Show only error and pageerror entries")
@browser_command_options
@handle_common_errors
@pack_command_params
def console_log(
    level: str | None,
    text_filter: str | None,
    limit: int,
    clear: bool,
    errors_only: bool,
    params: CommandParams,
) -> None:
    """Display captured browser console messages and page errors.

    Captures console.log/warn/error/info/debug and uncaught page errors
    using Playwright event listeners. On first call, starts monitoring.
    Subsequent calls display accumulated entries.

    Examples:
        act browser console-log
        act browser console-log --level error
        act browser console-log --errors-only
        act browser console-log --filter "*TypeError*"
        act browser console-log --clear
        act browser console-log --json
    """
    prep = prepare_session(params, None)
    capture = get_or_create_capture(params.session_id)

    with command_session("console-log", prep.manager, prep.session_info, params) as nova_act:
        if not capture.is_attached:
            capture.attach(get_active_page(nova_act, prep.session_info))
            if clear:
                capture.clear()
                echo_success("Console capture started and cleared")
                return
            echo_success(
                "Console monitoring started",
                details={"message": "Run commands, then re-run console-log to see messages"},
            )
            return

        if clear:
            capture.clear()
            echo_success("Console log cleared")
            return

        entries = capture.get_entries(level=level, text_filter=text_filter, errors_only=errors_only, limit=limit)
        _emit_entries(entries, capture.entry_count, params.session_id)


def _emit_entries(entries: list[ConsoleEntry], total: int, session_id: str) -> None:
    """Output entries in JSON or text format."""
    out = get_cli_stdout()
    if is_json_mode():
        payload = {
            "status": "success",
            "data": {
                "total_captured": total,
                "showing": len(entries),
                "entries": [_entry_to_dict(e) for e in entries],
            },
        }
        click.echo(_json.dumps(payload), file=out)
    else:
        click.echo("status: success", file=out)
        click.echo(f"total_captured: {total}", file=out)
        click.echo(f"showing: {len(entries)}", file=out)
        if entries:
            click.echo(f"{'LEVEL':<10} {'MESSAGE':<80} SOURCE", file=out)
            for entry in entries:
                click.echo(_format_entry_line(entry), file=out)
        else:
            click.echo("No matching entries", file=out)
