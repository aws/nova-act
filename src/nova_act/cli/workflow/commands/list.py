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
"""List command for listing local workflows."""

from typing import Dict

import click
from boto3 import Session

from nova_act.cli.core.identity import auto_detect_account_id
from nova_act.cli.core.region import get_default_region
from nova_act.cli.core.styling import command, header, secondary, value
from nova_act.cli.core.types import WorkflowInfo
from nova_act.cli.workflow.workflow_manager import WorkflowManager


def _display_region_header(region: str) -> None:
    """Display current region header."""
    click.echo(header(f"Workflows in {region}"))
    click.echo()


def _display_workflow_table(workflows: Dict[str, WorkflowInfo]) -> None:
    """Display workflows in simple list format."""
    for name, workflow_info in workflows.items():
        created_date = workflow_info.created_at.strftime("%Y-%m-%d")
        click.echo(f"{value(name)} {secondary(f'({created_date})')}")


def _display_footer() -> None:
    """Display footer with show command reference."""
    click.echo()
    click.echo(f"Use {command('act workflow show -n <name>')} for detailed information.")
    click.echo()


@click.command()
@click.option("--region", help="AWS region to query")
def list(region: str | None = None) -> None:
    """List all configured workflows."""
    # Create session at command boundary
    session = Session()

    effective_region = region or get_default_region()
    account_id = auto_detect_account_id(session=session, region=effective_region)
    workflow_manager = WorkflowManager(session=session, region=effective_region, account_id=account_id)
    workflows = workflow_manager.list_workflows()

    if not workflows:
        click.echo(
            f"{secondary('No workflows found.')} Use {command('act workflow create')} to create your first workflow."
        )
        click.echo()
        return

    _display_region_header(effective_region)
    _display_workflow_table(workflows)
    _display_footer()
