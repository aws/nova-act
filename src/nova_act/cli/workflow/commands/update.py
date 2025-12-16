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
"""Update command for Nova Act CLI workflows."""

import click
from boto3 import Session

from nova_act.cli.core.identity import auto_detect_account_id
from nova_act.cli.core.region import get_default_region
from nova_act.cli.core.styling import command, secondary, styled_error_exception, success, value
from nova_act.cli.workflow.utils.arn import (
    extract_workflow_definition_name_from_arn,
    validate_workflow_definition_arn,
)
from nova_act.cli.workflow.utils.console import build_nova_act_workflow_console_url
from nova_act.cli.workflow.workflow_manager import WorkflowManager


def _validate_workflow_exists(name: str, region: str, workflow_manager: WorkflowManager) -> str:
    """Validate workflow exists and return current ARN for comparison."""
    try:
        workflow = workflow_manager.get_workflow(name)
        return workflow.workflow_definition_arn or "Not set"
    except Exception as e:
        raise styled_error_exception(
            f"Workflow '{name}' not found in configuration.\n" f"Use 'act workflow list' to see available workflows."
        ) from e


def _validate_arn_format(arn: str) -> None:
    """Validate ARN format and structure."""
    try:
        validate_workflow_definition_arn(arn)
    except ValueError as e:
        raise styled_error_exception(f"Invalid WorkflowDefinition ARN: {str(e)}\n")


def _display_update_success(name: str, region: str, old_arn: str, new_arn: str) -> None:
    """Display workflow update success with before/after comparison."""
    click.echo(f"Updated workflow '{value(name)}' WorkflowDefinition ARN in region '{value(region)}':")
    click.echo(f"  {secondary(text='Old:')} {secondary(text=old_arn)}")
    click.echo(f"  {secondary(text='New:')} {value(text=new_arn)}")
    workflow_name = extract_workflow_definition_name_from_arn(new_arn)
    console_url = build_nova_act_workflow_console_url(region, workflow_name)
    click.echo(f"  {secondary(text='Console URL:')} {value(text=console_url)}")
    click.echo()
    success(message=f"✅ Workflow '{name}' updated successfully!")
    click.echo(f"Use {command(text=f'act workflow show --name {name}')} for full details.")
    click.echo()


@click.command()
@click.option("--name", "-n", required=True, help="Name of the workflow to update")
@click.option(
    "--workflow-definition-arn", required=True, help="New WorkflowDefinition ARN to associate with the workflow"
)
@click.option("--region", help="Region for WorkflowDefinition (defaults to config default_region)")
def update(name: str, workflow_definition_arn: str, region: str | None = None) -> None:
    """Update an existing workflow's WorkflowDefinition ARN for a specific region."""
    # Create session at command boundary
    session = Session()

    effective_region = region or get_default_region()
    account_id = auto_detect_account_id(session=session, region=effective_region)
    workflow_manager = WorkflowManager(session=session, region=effective_region, account_id=account_id)

    # Validate inputs
    old_arn = _validate_workflow_exists(name=name, region=effective_region, workflow_manager=workflow_manager)
    _validate_arn_format(arn=workflow_definition_arn)

    # Perform update
    workflow_manager.update_workflow_definition_arn(name=name, workflow_definition_arn=workflow_definition_arn)
    _display_update_success(name=name, region=effective_region, old_arn=old_arn, new_arn=workflow_definition_arn)
