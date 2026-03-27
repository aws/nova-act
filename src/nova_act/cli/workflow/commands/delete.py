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

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from nova_act.cli.core.exceptions import ConfigurationError, WorkflowError
from nova_act.cli.core.styling import secondary, styled_error_exception, success, value, warning

if TYPE_CHECKING:
    from boto3 import Session

    from nova_act.cli.core.types import WorkflowInfo


def _display_deletion_summary(name: str, region: str, cleanup: bool = False) -> None:
    """Display summary of what will be deleted."""
    click.echo(f"{secondary('Workflow to delete:')} {value(name)}")
    click.echo(f"{secondary('Target region:')} {value(region)}")
    if cleanup:
        click.echo(f"{secondary('Actions:')}")
        click.echo(f"  {secondary('1. Delete AgentCore runtime (if deployed)')}")
        click.echo(f"  {secondary('2. Delete WorkflowDefinition (if exists)')}")
        click.echo(f"  {secondary('3. Remove from local configuration')}")
    else:
        click.echo(f"{secondary('Action:')} {secondary('Remove from configuration')}")


def _confirm_deletion(force: bool) -> bool:
    """Handle deletion confirmation prompt."""
    if not force:
        if not click.confirm("Are you sure you want to proceed?"):
            click.echo(secondary("Operation cancelled"))
            return False
    return True


def _delete_agentcore_runtime(workflow: WorkflowInfo, session: Session, region: str) -> None:
    """Delete AgentCore runtime for a workflow. Logs warning on failure."""
    if not workflow.deployments.agentcore:
        click.echo(f"  {secondary('- No AgentCore runtime to delete')}")
        return
    try:
        from nova_act.cli.core.clients.agentcore.client import AgentCoreClient

        agentcore_client = AgentCoreClient(session=session, region=region)
        agentcore_client.delete_agent_runtime(agent_runtime_arn=workflow.deployments.agentcore.deployment_arn)
        click.echo(f"  {secondary('✓ Deleted AgentCore runtime')}")
    except Exception as e:
        warning(f"  ⚠ Failed to delete AgentCore runtime: {e}")


def _delete_workflow_definition(workflow: WorkflowInfo, session: Session, region: str) -> None:
    """Delete WorkflowDefinition for a workflow. Logs warning on failure."""
    if not workflow.workflow_definition_arn:
        click.echo(f"  {secondary('- No WorkflowDefinition to delete')}")
        return
    try:
        from nova_act.cli.core.clients.nova_act.client import NovaActClient
        from nova_act.cli.core.clients.nova_act.types import DeleteWorkflowDefinitionRequest

        nova_act_client = NovaActClient(boto_session=session, region_name=region)
        nova_act_client.delete_workflow_definition(
            request=DeleteWorkflowDefinitionRequest(workflowDefinitionName=workflow.name)
        )
        click.echo(f"  {secondary('✓ Deleted WorkflowDefinition')}")
    except Exception as e:
        warning(f"  ⚠ Failed to delete WorkflowDefinition: {e}")


def _cleanup_aws_resources(workflow: WorkflowInfo, session: Session, region: str) -> None:
    """Delete AWS resources associated with a workflow. Best-effort: logs warnings and continues on failure."""
    _delete_agentcore_runtime(workflow=workflow, session=session, region=region)
    _delete_workflow_definition(workflow=workflow, session=session, region=region)


@click.command()
@click.option("--name", "-n", required=True, help="Name of the workflow to delete")
@click.option("--region", help="AWS region to delete WorkflowDefinition from (defaults to configured region)")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
@click.option(
    "--cleanup",
    is_flag=True,
    default=False,
    help="Delete AWS resources (runtime + WorkflowDefinition) before removing local config",
)
def delete(name: str, region: str | None = None, force: bool = False, cleanup: bool = False) -> None:
    """Delete a workflow from configuration."""
    try:
        # Lazy-import heavy dependencies at call site
        from boto3 import Session

        from nova_act.cli.core.identity import auto_detect_account_id
        from nova_act.cli.core.region import get_default_region
        from nova_act.cli.workflow.workflow_manager import WorkflowManager

        # Create session at command boundary
        session = Session()

        target_region = region or get_default_region()
        account_id = auto_detect_account_id(session=session, region=target_region)
        workflow_manager = WorkflowManager(session=session, region=target_region, account_id=account_id)

        _display_deletion_summary(name=name, region=target_region, cleanup=cleanup)

        if not _confirm_deletion(force=force):
            return

        # Cleanup AWS resources before local config deletion
        if cleanup:
            workflow = workflow_manager.get_workflow(name=name)
            click.echo(f"\n{secondary('Cleaning up AWS resources...')}")
            _cleanup_aws_resources(workflow=workflow, session=session, region=target_region)
            click.echo()

        # Remove from local config
        workflow_manager.delete_workflow(name=name)
        success(f"✅ Removed '{name}' from configuration")
        click.echo()

    except (WorkflowError, ConfigurationError) as e:
        raise styled_error_exception(str(e))
    except Exception as e:
        raise styled_error_exception(f"Unexpected error: {str(e)}") from e
