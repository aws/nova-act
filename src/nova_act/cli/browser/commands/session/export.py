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
"""Session export command — export structured session history for agent consumption."""

from __future__ import annotations

import base64
import json
import logging
import shutil
from pathlib import Path

import click
import yaml

from nova_act.cli.browser.services.session_recorder import CommandEntry, SessionManifest, get_recorder
from nova_act.cli.browser.utils.decorators import json_option
from nova_act.cli.core.output import echo_success, exit_with_error, get_cli_stdout

logger = logging.getLogger(__name__)

# Commands that use AI inference (act/act_get under the hood)
AI_COMMANDS = frozenset(
    {"execute", "ask", "fill_form", "fill-form", "scroll_to", "scroll-to", "wait_for", "wait-for", "verify"}
)


def _classify_command(command_name: str) -> str:
    """Classify a command as ai_command or playwright_operation."""
    normalized = command_name.replace("-", "_")
    return "ai_command" if normalized in {c.replace("-", "_") for c in AI_COMMANDS} else "playwright_operation"


def _enrich_entry(entry: CommandEntry) -> CommandEntry:
    """Add type classification and hints to a manifest entry."""
    cmd = entry.get("command", "")
    cmd_type = _classify_command(cmd)
    enriched: CommandEntry = {
        "command": cmd,
        "type": cmd_type,
        "args": entry.get("args", {}),
        "timestamp": entry.get("timestamp", ""),
    }
    if "duration_ms" in entry:
        enriched["duration_ms"] = entry["duration_ms"]
    if entry.get("result_summary"):
        enriched["result"] = entry["result_summary"]
    if cmd_type == "ai_command" and entry.get("steps_file"):
        enriched["steps_file"] = entry["steps_file"]
        # Try to load steps summary inline
        try:
            steps_path = Path(entry["steps_file"])
            if steps_path.exists():
                enriched["steps_summary"] = yaml.safe_load(steps_path.read_text())
        except Exception:
            pass
    if entry.get("screenshots"):
        enriched["screenshots"] = entry["screenshots"]
    if entry.get("log_file"):
        enriched["log_file"] = entry["log_file"]
    return enriched


def _embed_screenshots(entry: CommandEntry) -> CommandEntry:
    """Embed screenshot files as base64 in the entry."""
    screenshots = entry.get("screenshots", {})
    if not screenshots:
        return entry
    embedded: dict[str, str] = {}
    for key, path_str in screenshots.items():
        if not path_str:
            continue
        p = Path(path_str)
        if p.exists() and p.suffix in (".png", ".jpg", ".jpeg"):
            try:
                embedded[key] = base64.b64encode(p.read_bytes()).decode("ascii")
            except Exception:
                embedded[key] = f"<error reading {path_str}>"
        else:
            embedded[key] = str(path_str)  # keep path reference if file missing
    if embedded:
        entry = CommandEntry(**entry)
        entry["screenshots_base64"] = embedded
    return entry


def _build_export(manifest: SessionManifest, include_screenshots: bool) -> dict[str, object]:
    """Build the full export payload from a recorder manifest."""
    commands = manifest["commands"]
    enriched = [_enrich_entry(e) for e in commands]
    if include_screenshots:
        enriched = [_embed_screenshots(e) for e in enriched]

    total_duration_ms = sum(e.get("duration_ms", 0) for e in enriched)
    return {
        "session_id": manifest.get("session_id", ""),
        "created_at": manifest.get("started_at", ""),
        "total_commands": len(enriched),
        "total_duration_ms": round(total_duration_ms, 1),
        "commands": enriched,
    }


def _copy_resource(src_path: str, dest_dir: Path) -> str | None:
    """Copy a resource file into dest_dir. Returns relative path from report root, or None if missing."""
    src = Path(src_path)
    if not src.exists():
        return None
    dest = dest_dir / src.name
    # Handle name collisions by appending a counter
    counter = 1
    while dest.exists():
        dest = dest_dir / f"{src.stem}_{counter}{src.suffix}"
        counter += 1
    shutil.copy2(str(src), str(dest))
    return f"{dest_dir.name}/{dest.name}"


def _build_metadata_section(export_data: dict[str, object]) -> list[str]:
    """Build the metadata section of the markdown report."""
    sid = export_data.get("session_id", "unknown")
    total_ms = export_data.get("total_duration_ms", 0)
    assert isinstance(total_ms, (int, float))
    return [
        f"# Session Report: {sid}",
        "",
        "## Session Metadata",
        "",
        f"- **Session ID**: {sid}",
        f"- **Created**: {export_data.get('created_at', 'N/A')}",
        f"- **Total Commands**: {export_data.get('total_commands', 0)}",
        f"- **Total Duration**: {total_ms}ms ({total_ms / 1000:.1f}s)",
        "",
    ]


def _build_command_section(index: int, cmd: CommandEntry, resources: dict[str, str | None]) -> list[str]:
    """Build the markdown section for a single command."""
    cmd_name = cmd.get("command", "unknown")
    cmd_type = cmd.get("type", "unknown")
    lines: list[str] = [
        f"### {index + 1}. {cmd_name}",
        "",
        f"- **Type**: {cmd_type}",
    ]
    if cmd.get("timestamp"):
        lines.append(f"- **Timestamp**: {cmd['timestamp']}")
    if "duration_ms" in cmd:
        lines.append(f"- **Duration**: {cmd['duration_ms']}ms")
    if cmd.get("args"):
        lines.append(f"- **Args**: `{json.dumps(cmd['args'])}`")
    if cmd.get("result"):
        lines.append(f"- **Result**: `{json.dumps(cmd['result'])}`")

    # Resource references
    if resources.get("steps_file"):
        lines.append(f"- **Steps**: [{resources['steps_file']}]({resources['steps_file']})")
    elif cmd.get("steps_file"):
        lines.append(f"- **Steps**: *(file not found: {cmd['steps_file']})*")

    if resources.get("log_file"):
        lines.append(f"- **Log**: [{resources['log_file']}]({resources['log_file']})")
    elif cmd.get("log_file"):
        lines.append(f"- **Log**: *(file not found: {cmd['log_file']})*")

    for key, path_str in cmd.get("screenshots", {}).items():
        rel = resources.get(f"screenshot_{key}")
        if rel:
            if rel.endswith((".png", ".jpg", ".jpeg")):
                lines.append(f"- **{key}**: ![{key}]({rel})")
            else:
                lines.append(f"- **{key}**: [{rel}]({rel})")
        else:
            lines.append(f"- **{key}**: *(file not found: {path_str})*")

    lines.append("")
    return lines


def _generate_report_markdown(
    export_data: dict[str, object], copied_resources: dict[int, dict[str, str | None]]
) -> str:
    """Generate a structured markdown report from export data and copied resource paths."""
    lines = _build_metadata_section(export_data)

    commands = export_data.get("commands", [])
    assert isinstance(commands, list)
    if not commands:
        lines.append("*No commands recorded.*")
        return "\n".join(lines)

    lines.append("## Commands")
    lines.append("")

    for i, cmd in enumerate(commands):
        lines.extend(_build_command_section(i, cmd, copied_resources.get(i, {})))

    return "\n".join(lines)


def _copy_command_resources(
    cmd: CommandEntry,
    screenshots_dir: Path,
    steps_dir: Path,
    logs_dir: Path,
) -> dict[str, str | None]:
    """Copy a single command's resource files into the report directory structure.

    Returns a dict mapping resource keys to their relative paths from the report root.
    """
    resources: dict[str, str | None] = {}

    if cmd.get("steps_file"):
        steps_dir.mkdir(parents=True, exist_ok=True)
        resources["steps_file"] = _copy_resource(cmd["steps_file"], steps_dir)

    if cmd.get("log_file"):
        logs_dir.mkdir(parents=True, exist_ok=True)
        resources["log_file"] = _copy_resource(cmd["log_file"], logs_dir)

    for key, path_str in cmd.get("screenshots", {}).items():
        if path_str:
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            resources[f"screenshot_{key}"] = _copy_resource(path_str, screenshots_dir)

    return resources


def _build_report(export_data: dict[str, object], output_dir: Path) -> str:
    """Build a full report directory with markdown and copied resources. Returns the report path."""
    output_dir.mkdir(parents=True, exist_ok=True)

    screenshots_dir = output_dir / "screenshots"
    steps_dir = output_dir / "steps"
    logs_dir = output_dir / "logs"

    copied_resources: dict[int, dict[str, str | None]] = {}
    commands = export_data.get("commands", [])
    assert isinstance(commands, list)
    for i, cmd in enumerate(commands):
        resources = _copy_command_resources(cmd, screenshots_dir, steps_dir, logs_dir)
        if resources:
            copied_resources[i] = resources

    markdown = _generate_report_markdown(export_data, copied_resources)
    report_path = output_dir / "report.md"
    report_path.write_text(markdown, encoding="utf-8")
    return str(report_path)


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
