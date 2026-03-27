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
"""List command for listing local and remote workflows."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional

import click

from nova_act.cli.core.styling import command, header, secondary, value, warning

if TYPE_CHECKING:
    from nova_act.cli.core.clients.nova_act.types import WorkflowDefinitionSummary
    from nova_act.cli.core.types import WorkflowInfo

logger = logging.getLogger(__name__)

STATUS_SYNCED = "synced"
STATUS_REMOTE = "remote"
STATUS_LOCAL = "local"


@dataclass
class MergedWorkflow:
    """A workflow entry merged from local and/or remote sources."""

    name: str
    status: str
    created_date: str
    source: str  # "local", "remote", or "both"


def _merge_workflows(
    local_workflows: Dict[str, WorkflowInfo],
    remote_workflows: List[WorkflowDefinitionSummary],
) -> List[MergedWorkflow]:
    """Merge local and remote workflows into a unified list."""
    merged: Dict[str, MergedWorkflow] = {}

    for name, wf in local_workflows.items():
        merged[name] = MergedWorkflow(
            name=name,
            status=STATUS_LOCAL,
            created_date=wf.created_at.strftime("%Y-%m-%d"),
            source="local",
        )

    for remote_wf in remote_workflows:
        if remote_wf.status == "DELETING":
            continue
        name = remote_wf.workflowDefinitionName
        if name in merged:
            merged[name].status = STATUS_SYNCED
            merged[name].source = "both"
        else:
            merged[name] = MergedWorkflow(
                name=name,
                status=STATUS_REMOTE,
                created_date=remote_wf.createdAt.strftime("%Y-%m-%d"),
                source="remote",
            )

    return sorted(merged.values(), key=lambda w: w.name)


def _status_display(status: str) -> str:
    """Format status for display."""
    icons = {STATUS_SYNCED: "●", STATUS_REMOTE: "☁", STATUS_LOCAL: "◌"}
    return f"{icons.get(status, '?')} {status}"


def _display_region_header(region: str) -> None:
    """Display current region header."""
    click.echo(header(f"Workflows in {region}"))
    click.echo()


def _display_workflow_table(workflows: Dict[str, WorkflowInfo]) -> None:
    """Display workflows in simple list format (local-only fallback)."""
    for name, workflow_info in workflows.items():
        created_date = workflow_info.created_at.strftime("%Y-%m-%d")
        click.echo(f"{value(name)} {secondary(f'({created_date})')}")


def _display_merged_table(merged: List[MergedWorkflow]) -> None:
    """Display merged workflow table with status indicators."""
    # Calculate column widths
    name_width = max((len(w.name) for w in merged), default=10)
    name_width = max(name_width, 4)  # minimum "NAME" header width

    # Header
    click.echo(f"  {'NAME':<{name_width}}  {'STATUS':<10}  {'CREATED'}")
    click.echo(f"  {'─' * name_width}  {'─' * 10}  {'─' * 10}")

    for wf in merged:
        status_str = _status_display(wf.status)
        name_padded = wf.name + " " * (name_width - len(wf.name))
        click.echo(f"  {value(name_padded)}  {secondary(status_str):<10}  {secondary(wf.created_date)}")


def _filter_workflows(merged: List[MergedWorkflow], *, show_local: bool, show_remote: bool) -> List[MergedWorkflow]:
    """Filter merged workflows based on --local or --remote flags."""
    if show_local:
        return [w for w in merged if w.status in (STATUS_LOCAL, STATUS_SYNCED)]
    if show_remote:
        return [w for w in merged if w.status in (STATUS_REMOTE, STATUS_SYNCED)]
    return merged


def _display_footer() -> None:
    """Display footer with legend and command reference."""
    click.echo()
    click.echo(secondary("  ● synced  — exists both locally and in AWS"))
    click.echo(secondary("  ☁ remote  — exists only in AWS (not local)"))
    click.echo(secondary("  ◌ local   — exists only locally (not yet deployed)"))
    click.echo()
    click.echo(f"  Use {command('act workflow show -n <name>')} for detailed information.")
    click.echo()


def _display_footer_local_only() -> None:
    """Display footer for local-only view."""
    click.echo()
    click.echo(f"Use {command('act workflow show -n <name>')} for detailed information.")
    click.echo()


@click.command()
@click.option("--region", help="AWS region to query")
@click.option("--local", "show_local", is_flag=True, help="Show only local and synced workflows")
@click.option("--remote", "show_remote", is_flag=True, help="Show only remote and synced workflows")
def list(region: str | None = None, show_local: bool = False, show_remote: bool = False) -> None:
    """List all configured workflows."""
    if show_local and show_remote:
        raise click.UsageError("--local and --remote are mutually exclusive.")

    # Lazy-import heavy dependencies at call site
    from boto3 import Session

    from nova_act.cli.core.identity import auto_detect_account_id
    from nova_act.cli.core.region import get_default_region
    from nova_act.cli.workflow.workflow_manager import WorkflowManager

    session = Session()
    effective_region = region or get_default_region()
    account_id = auto_detect_account_id(session=session, region=effective_region)
    workflow_manager = WorkflowManager(session=session, region=effective_region, account_id=account_id)

    local_workflows = workflow_manager.list_workflows()

    # Try to fetch remote workflows
    remote_workflows: Optional[List[WorkflowDefinitionSummary]] = None
    try:
        remote_workflows = workflow_manager.list_remote_workflows()
    except Exception as e:
        logger.debug(f"Failed to fetch remote workflows: {e}")
        warning(f"⚠ Could not fetch remote workflows: {e}")
        click.echo(secondary("  Showing local workflows only."))
        click.echo()

    # If remote fetch succeeded, show merged view
    if remote_workflows is not None:
        merged = _merge_workflows(local_workflows, remote_workflows)
        merged = _filter_workflows(merged, show_local=show_local, show_remote=show_remote)
        if not merged:
            no_workflows_msg = f"{secondary('No workflows found.')}"
            create_hint = f"Use {command('act workflow create')} to create your first workflow."
            click.echo(f"{no_workflows_msg} {create_hint}")
            click.echo()
            return

        _display_region_header(effective_region)
        _display_merged_table(merged)
        _display_footer()
        return

    # Fallback: local-only view
    if not local_workflows:
        click.echo(
            f"{secondary('No workflows found.')} Use {command('act workflow create')} to create your first workflow."
        )
        click.echo()
        return

    _display_region_header(effective_region)
    _display_workflow_table(local_workflows)
    _display_footer_local_only()
