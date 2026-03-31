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
"""List workflow runs command."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import click

from nova_act.cli.core.styling import header, secondary, styled_error_exception, value
from nova_act.cli.workflow.commands.error_handlers import handle_client_error, handle_credential_error

if TYPE_CHECKING:
    from nova_act.cli.core.clients.nova_act.types import WorkflowRunSummary


def _format_duration(run: WorkflowRunSummary) -> str:
    """Format duration from startedAt/endedAt."""
    if not run.endedAt:
        return "running"
    delta = run.endedAt - run.startedAt
    total_seconds = int(delta.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds}s"
    minutes, seconds = divmod(total_seconds, 60)
    if minutes < 60:
        return f"{minutes}m {seconds}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def _display_runs_table(runs: list[WorkflowRunSummary], name: str) -> None:
    """Display workflow runs in a table."""
    click.echo(header(f"Workflow Runs for '{name}'"))
    click.echo()

    if not runs:
        click.echo(secondary("  No runs found."))
        return

    # Column widths
    id_width = max(len(r.workflowRunId[:8]) for r in runs)
    status_width = max(len(r.status) for r in runs)

    click.echo(f"  {'ID':<{id_width}}  {'STATUS':<{status_width}}  {'STARTED':<20}  DURATION")
    click.echo(f"  {'─' * id_width}  {'─' * status_width}  {'─' * 20}  {'─' * 10}")

    for run in runs:
        run_id = run.workflowRunId[:8]
        started = run.startedAt.strftime("%Y-%m-%d %H:%M:%S")
        duration = _format_duration(run)
        click.echo(
            f"  {value(run_id):<{id_width}}  {secondary(run.status):<{status_width}}"
            f"  {secondary(started):<20}  {secondary(duration)}"
        )

    click.echo()


@click.command("list-runs")
@click.option("--name", "-n", required=True, help="Workflow name")
@click.option(
    "--status",
    type=click.Choice(["RUNNING", "SUCCEEDED", "FAILED", "TIMED_OUT"], case_sensitive=False),
    help="Filter by status",
)
@click.option("--limit", default=20, type=int, help="Maximum runs to display (default: 20)")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--region", help="AWS region")
def list_runs(
    name: str,
    status: str | None = None,
    limit: int = 20,
    as_json: bool = False,
    region: str | None = None,
) -> None:
    """List runs for a workflow."""
    try:
        from boto3 import Session
        from botocore.exceptions import ClientError, NoCredentialsError

        from nova_act.cli.core.clients.nova_act.client import NovaActClient
        from nova_act.cli.core.identity import auto_detect_account_id
        from nova_act.cli.core.region import get_default_region

        session = Session()
        effective_region = region or get_default_region()
        account_id = auto_detect_account_id(session=session, region=effective_region)

        client = NovaActClient(boto_session=session, region_name=effective_region)
        runs = client.list_workflow_runs(name)

        # Filter by status if requested
        if status:
            runs = [r for r in runs if r.status == status.upper()]

        # Apply limit
        runs = runs[:limit]

        if as_json:
            output = [r.model_dump(mode="json") for r in runs]
            click.echo(json.dumps(output, indent=2, default=str))
        else:
            _display_runs_table(runs, name)

    except NoCredentialsError:
        handle_credential_error()

    except ClientError as e:
        handle_client_error(
            error=e, workflow_name=name, region=effective_region, account_id=account_id, context="listing workflow runs"
        )

    except Exception as e:
        raise styled_error_exception(message=f"Unexpected error: {str(e)}") from e
