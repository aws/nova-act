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
"""Delete command for Nova Act CLI workflows."""

import click
from boto3 import Session

from nova_act.cli.core.exceptions import ConfigurationError, WorkflowError
from nova_act.cli.core.identity import auto_detect_account_id
from nova_act.cli.core.region import get_default_region
from nova_act.cli.core.styling import secondary, styled_error_exception, success, value
from nova_act.cli.workflow.workflow_manager import WorkflowManager


def _display_deletion_summary(name: str, region: str) -> None:
    """Display summary of what will be deleted."""
    click.echo(f"{secondary('Workflow to delete:')} {value(name)}")
    click.echo(f"{secondary('Target region:')} {value(region)}")
    click.echo(f"{secondary('Action:')} {secondary('Remove from configuration')}")


def _confirm_deletion(force: bool) -> bool:
    """Handle deletion confirmation prompt."""
    if not force:
        if not click.confirm("Are you sure you want to proceed?"):
            click.echo(secondary("Operation cancelled"))
            return False
    return True


@click.command()
@click.option("--name", "-n", required=True, help="Name of the workflow to delete")
@click.option("--region", help="AWS region to delete WorkflowDefinition from (defaults to configured region)")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
def delete(name: str, region: str | None = None, force: bool = False) -> None:
    """Delete a workflow from configuration."""
    try:
        # Create session at command boundary
        session = Session()

        target_region = region or get_default_region()
        account_id = auto_detect_account_id(session=session, region=target_region)
        workflow_manager = WorkflowManager(session=session, region=target_region, account_id=account_id)

        _display_deletion_summary(name=name, region=target_region)

        if not _confirm_deletion(force=force):
            return

        # Remove from local config only to avoid unintentional AWS resource deletion
        workflow_manager.delete_workflow(name=name)
        success(f"✅ Removed '{name}' from configuration")
        click.echo()

    except (WorkflowError, ConfigurationError) as e:
        raise styled_error_exception(str(e))
    except Exception as e:
        raise styled_error_exception(f"Unexpected error: {str(e)}") from e
