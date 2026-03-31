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
"""Record-show command — display session recording manifest."""

from __future__ import annotations

import json

import click

from nova_act.cli.browser.services.session_recorder import (
    get_recorder,
)
from nova_act.cli.browser.utils.decorators import json_option
from nova_act.cli.core.output import echo_success, get_cli_stdout


@click.command(name="record-show")
@click.option("--session-id", default="default", help="Session ID (default: 'default')")
@click.option("--limit", type=int, default=None, help="Show last N commands only")
@click.option("--summary", is_flag=True, help="Condensed summary view")
@json_option
def record_show(session_id: str, limit: int | None, summary: bool) -> None:
    """Display session recording manifest.

    Shows all commands recorded in the session, with timestamps, durations,
    and artifact paths. Use --json for structured output (critical for agents).

    Examples:
        act browser session record-show
        act browser session record-show --session-id my-session
        act browser session record-show --limit 5 --json
        act browser session record-show --summary
    """
    recorder = get_recorder(session_id)
    manifest = recorder.get_manifest()
    commands = recorder.get_commands(limit=limit)

    if not commands:
        echo_success("No commands recorded", details={"session_id": session_id})
        return

    from nova_act.cli.core.json_output import is_json_mode

    out = get_cli_stdout()
    if is_json_mode():
        output = {
            "session_id": manifest.get("session_id"),
            "started_at": manifest.get("started_at"),
            "last_updated": manifest.get("last_updated"),
            "total_commands": len(manifest.get("commands", [])),
            "commands": commands,
        }
        click.echo(json.dumps(output, indent=2), file=out)
        return

    if summary:
        echo_success(
            f"Session recording ({len(commands)} commands)",
            details={
                "Started": manifest.get("started_at", "unknown"),
                "Commands": ", ".join(c["command"] for c in commands),
            },
        )
        return

    # Detailed view
    details: dict[str, str] = {
        "Started": manifest.get("started_at", "unknown"),
        "Total commands": str(len(manifest.get("commands", []))),
    }
    for i, cmd in enumerate(commands, 1):
        duration = f" ({cmd['duration_ms']:.0f}ms)" if "duration_ms" in cmd else ""
        details[f"  [{i}] {cmd['command']}"] = f"{cmd.get('timestamp', '')}{duration}"

    echo_success(f"Session recording ({len(commands)} commands)", details=details)
