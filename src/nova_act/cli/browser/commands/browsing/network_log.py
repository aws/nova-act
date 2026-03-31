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
"""Network-log command — display captured network requests/responses."""

from __future__ import annotations

import json as _json
from typing import TYPE_CHECKING

import click

from nova_act.cli.browser.services.network_capture import (
    NetworkCaptureService,
    NetworkEntry,
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

# Module-level registry: session_id -> NetworkCaptureService
_capture_registry: dict[str, NetworkCaptureService] = {}


def get_or_create_capture(session_id: str) -> NetworkCaptureService:
    """Get existing capture service or create a new one for the session."""
    if session_id not in _capture_registry:
        _capture_registry[session_id] = NetworkCaptureService()
    return _capture_registry[session_id]


def _entry_to_dict(entry: NetworkEntry) -> dict[str, object]:
    result: dict[str, object] = {
        "method": entry.method,
        "url": entry.url,
        "status": entry.status,
        "resource_type": entry.resource_type,
        "duration_ms": entry.duration_ms,
        "size": entry.size,
    }
    if entry.failed:
        result["failed"] = True
        result["failure_text"] = entry.failure_text
    return result


def _format_entry_line(entry: NetworkEntry) -> str:
    status = str(entry.status) if entry.status else ("FAIL" if entry.failed else "---")
    duration = f"{entry.duration_ms}ms" if entry.duration_ms is not None else "---"
    return f"{entry.method:<6} {status:<5} {duration:<10} {entry.resource_type:<12} {entry.url}"


@click.command("network-log")
@click.option("--filter", "url_filter", default=None, help="Glob pattern to filter URLs (e.g. '*api*')")
@click.option("--method", default=None, help="Filter by HTTP method (GET, POST, etc.)")
@click.option("--status", default=None, help="Filter by status code (200, 4xx, 5xx, >=400)")
@click.option("--limit", default=50, type=int, help="Max entries to display (default: 50)")
@click.option("--clear", is_flag=True, help="Clear captured entries")
@browser_command_options
@handle_common_errors
@pack_command_params
def network_log(
    url_filter: str | None,
    method: str | None,
    status: str | None,
    limit: int,
    clear: bool,
    params: CommandParams,
) -> None:
    """Display captured network requests and responses.

    Captures HTTP traffic using Playwright event listeners. On first call,
    starts monitoring. Subsequent calls display accumulated entries.

    Examples:
        act browser network-log
        act browser network-log --filter "*api*" --method POST
        act browser network-log --status 4xx --limit 20
        act browser network-log --clear
        act browser network-log --json
    """
    prep = prepare_session(params, None)
    capture = get_or_create_capture(params.session_id)

    with command_session("network-log", prep.manager, prep.session_info, params) as nova_act:
        # Attach capture if not already attached
        if not capture.is_attached:
            capture.attach(get_active_page(nova_act, prep.session_info))
            if clear:
                capture.clear()
                echo_success("Network capture started and cleared")
                return
            echo_success(
                "Network monitoring started",
                details={"message": "Run commands, then re-run network-log to see traffic"},
            )
            return

        if clear:
            capture.clear()
            echo_success("Network log cleared")
            return

        entries = capture.get_entries(url_filter=url_filter, method=method, status=status, limit=limit)
        _emit_entries(entries, capture.entry_count, params.session_id)


def _emit_entries(entries: list[NetworkEntry], total: int, session_id: str) -> None:
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
            click.echo(f"{'METHOD':<6} {'CODE':<5} {'DURATION':<10} {'TYPE':<12} URL", file=out)
            for entry in entries:
                click.echo(_format_entry_line(entry), file=out)
        else:
            click.echo("No matching entries", file=out)
