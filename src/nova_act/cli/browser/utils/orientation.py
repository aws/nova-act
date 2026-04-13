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
"""Post-command orientation utilities: observe, snapshot, screenshot, and steps summary."""

from __future__ import annotations

import json as _json
import logging
from typing import TYPE_CHECKING

import click
import yaml
from playwright.sync_api import Error as PlaywrightError

from nova_act import NovaAct
from nova_act.cli.browser.services.browser_actions.utils import run_observe
from nova_act.cli.browser.services.session.models import SessionInfo
from nova_act.cli.browser.services.step_tracking import write_steps_summary
from nova_act.cli.browser.utils.log_capture import get_current_command_dir, get_log_dir
from nova_act.cli.browser.utils.session import get_active_page
from nova_act.cli.core.json_output import is_json_mode
from nova_act.cli.core.output import get_cli_stdout

if TYPE_CHECKING:
    from pathlib import Path

    from nova_act.cli.browser.services.intent_resolution.snapshot import SnapshotElement
    from nova_act.cli.browser.types import CommandParams

logger = logging.getLogger(__name__)


def emit_observe(nova_act: NovaAct) -> None:
    """Run observe and emit the layout to CLI output."""
    layout = run_observe(nova_act)
    out = get_cli_stdout()
    if not layout:
        if is_json_mode():
            click.echo(_json.dumps({"observe": {"error": "observe failed"}}), file=out)
        else:
            click.echo("observe: failed", file=out)
        return
    if is_json_mode():
        click.echo(_json.dumps({"observe": {"layout": layout}}), file=out)
    else:
        click.echo(f"observe.layout: {layout}", file=out)


def _capture_auto_snapshot(
    nova_act: NovaAct,
    session_info: SessionInfo,
    cmd_dir: "Path",
    command_name: str,
) -> dict[str, object]:
    """Capture accessibility snapshot and write to cmd_dir/snapshot.yaml."""
    from nova_act.cli.browser.services.intent_resolution import flatten_snapshot

    active_page = get_active_page(nova_act, session_info)
    tree = active_page.accessibility.snapshot()
    elements = flatten_snapshot(tree)
    snapshot_data = [{"ref": e.ref, "role": e.role, "name": e.name, "value": e.value} for e in elements if e.name]
    snapshot_path = cmd_dir / "snapshot.yaml"
    snapshot_path.write_text(yaml.dump(snapshot_data, default_flow_style=False, sort_keys=False))
    return {
        "snapshot_path": str(snapshot_path),
        "snapshot_summary": {
            "url": active_page.url,
            "title": active_page.title(),
            "interactive_elements": len(snapshot_data),
        },
    }


def _capture_auto_screenshot(
    nova_act: NovaAct,
    session_info: SessionInfo,
    cmd_dir: "Path",
) -> dict[str, object]:
    """Capture screenshot and write to cmd_dir/screenshot.png."""
    screenshot_path = cmd_dir / "screenshot.png"
    screenshot_bytes = get_active_page(nova_act, session_info).screenshot()
    screenshot_path.write_bytes(screenshot_bytes)
    return {"screenshot_path": str(screenshot_path)}


def auto_orientation(
    nova_act: NovaAct, session_info: SessionInfo, params: "CommandParams", command_name: str
) -> dict[str, object]:
    """Capture auto-snapshot and auto-screenshot after command execution.

    Returns metadata dict with snapshot_path, screenshot_path, and snapshot_summary.
    Files are written into the per-command subdirectory.
    """
    metadata: dict[str, object] = {}
    cmd_dir = get_current_command_dir()
    if cmd_dir is None:
        cmd_dir = get_log_dir(params.session_id)
    cmd_dir.mkdir(parents=True, exist_ok=True)

    if not params.no_snapshot:
        try:
            metadata.update(_capture_auto_snapshot(nova_act, session_info, cmd_dir, command_name))
        except (PlaywrightError, OSError):
            logger.debug("Auto-snapshot failed for command '%s'", command_name)

    if not params.no_screenshot:
        try:
            metadata.update(_capture_auto_screenshot(nova_act, session_info, cmd_dir))
        except (PlaywrightError, OSError, TypeError):
            logger.debug("Auto-screenshot failed for command '%s'", command_name)

    return metadata


def emit_steps_summary(
    nova_act: NovaAct,
    params: "CommandParams",
    command_name: str,
    snapshots: list[list[SnapshotElement]],
) -> dict[str, object] | None:
    """Write steps summary from trajectory + monkey-patch snapshots. Returns metadata or None."""
    try:
        log_dir = get_log_dir(params.session_id)
        trajectory_dir = log_dir
        cmd_dir = get_current_command_dir()
        if cmd_dir is None:
            cmd_dir = log_dir
        return write_steps_summary(trajectory_dir, command_name, snapshots, cmd_dir)
    except (OSError, _json.JSONDecodeError, KeyError):
        logger.debug("Steps summary failed for command '%s'", command_name)
        return None
