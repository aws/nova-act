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
"""Session export command — thin CLI wrapper delegating to session_export service."""

from __future__ import annotations

import json
from pathlib import Path

import click
import yaml

from nova_act.cli.browser.services.session_export import _build_export, _build_report
from nova_act.cli.browser.services.session_recorder import get_recorder
from nova_act.cli.browser.utils.decorators import json_option
from nova_act.cli.core.output import echo_success, exit_with_error, get_cli_stdout


@click.command(name="export")
@click.option("--session-id", default="default", help="Session ID (default: 'default')")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save export to file")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "yaml"]),
    default="json",
    help="Output format (default: json)",
)
@click.option("--include-screenshots", is_flag=True, help="Embed screenshots as base64 (warning: large output)")
@click.option("--report", is_flag=True, help="Generate a structured markdown report with copied resources")
@click.option("--output-dir", type=click.Path(), default=None, help="Report output directory (requires --report)")
@json_option
def export(
    session_id: str, output: str | None, fmt: str, include_screenshots: bool, report: bool, output_dir: str | None
) -> None:
    """Export structured session history for agent consumption.

    Outputs every command executed in the session with type classification:
    - ai_command: Commands using AI inference (execute, ask, verify, etc.)
    - playwright_operation: Direct browser operations (goto, screenshot, etc.)

    Examples:
        act browser session export
        act browser session export --session-id my-session --format json
        act browser session export --output history.json --include-screenshots
        act browser session export --format yaml -o history.yaml
        act browser session export --report
        act browser session export --report --output-dir ./my-report
    """
    # Validate flag combinations
    if output_dir and not report:
        exit_with_error(
            "Invalid options",
            "--output-dir requires --report",
            suggestions=["Add --report flag: act browser session export --report --output-dir ./my-report"],
        )

    if report and fmt != "json":
        exit_with_error(
            "Invalid options",
            "--report cannot be combined with --format (report always outputs markdown)",
            suggestions=["Remove --format flag when using --report"],
        )

    recorder = get_recorder(session_id)
    manifest = recorder.get_manifest()
    commands = manifest["commands"]

    if report:
        # Build export data (no base64 embedding — we copy files instead)
        payload = _build_export(manifest, include_screenshots=False)
        report_dir = Path(output_dir) if output_dir else Path(f"./{session_id}_report")
        report_path = _build_report(payload, report_dir)
        echo_success(
            f"Report generated at {report_path}",
            details={
                "session_id": session_id,
                "commands": len(commands),
                "output_dir": str(report_dir),
            },
        )
        return

    if not commands:
        echo_success("No commands recorded", details={"session_id": session_id})
        return

    if include_screenshots:
        click.echo("⚠ --include-screenshots embeds image data as base64. Output may be very large.", err=True)

    payload = _build_export(manifest, include_screenshots)

    # Serialize
    if fmt == "yaml":
        serialized = yaml.dump(payload, default_flow_style=False, sort_keys=False)
    else:
        serialized = json.dumps(payload, indent=2)

    # Output
    if output:
        Path(output).write_text(serialized, encoding="utf-8")
        echo_success(
            f"Session exported to {output}",
            details={
                "session_id": session_id,
                "commands": len(commands),
            },
        )
    else:
        out = get_cli_stdout()
        click.echo(serialized, file=out)
