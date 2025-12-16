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
"""Show command for Nova Act CLI workflows."""

import sys

import click
from boto3 import Session

from nova_act.cli.core.exceptions import WorkflowError
from nova_act.cli.core.identity import auto_detect_account_id
from nova_act.cli.core.region import get_default_region
from nova_act.cli.core.styling import command, header, secondary, styled_error_exception, value
from nova_act.cli.core.types import WorkflowInfo
from nova_act.cli.workflow.utils.arn import extract_workflow_definition_name_from_arn
from nova_act.cli.workflow.utils.console import build_nova_act_workflow_console_url
from nova_act.cli.workflow.workflow_manager import WorkflowManager


def _display_workflow_info(workflow_info: WorkflowInfo, region: str) -> None:
    """Display all WorkflowInfo fields in key-value format."""
    click.echo(header("Workflow Details"))
    click.echo(f"{secondary('Name:')} {value(workflow_info.name)}")

    # Show directory path directly without existence check
    if workflow_info.directory_path and workflow_info.directory_path.strip():
        click.echo(f"{secondary('Directory:')} {value(workflow_info.directory_path)}")

    if workflow_info.created_at:
        click.echo(f"{secondary('Created:')} {value(workflow_info.created_at.strftime('%Y-%m-%d %H:%M:%S'))}")

    if workflow_info.workflow_definition_arn:
        click.echo(f"{secondary('Workflow Definition ARN:')} {value(workflow_info.workflow_definition_arn)}")
        workflow_name = extract_workflow_definition_name_from_arn(workflow_info.workflow_definition_arn)
        console_url = build_nova_act_workflow_console_url(region, workflow_name)
        click.echo(f"{secondary('Console URL:')} {value(console_url)}")

    if workflow_info.deployments.agentcore:
        deployment = workflow_info.deployments.agentcore
        click.echo(f"{secondary('AgentCore Deployment:')} {value(deployment.deployment_arn)}")
        click.echo(f"{secondary('Container Image:')} {value(deployment.image_uri)}")


@click.command()
@click.option("--name", "-n", required=True, help="Name of the workflow to show")
@click.option("--region", help="AWS region to query")
def show(name: str, region: str | None = None) -> None:
    """Show detailed information about a workflow."""
    try:
        # Create session at command boundary
        session = Session()

        effective_region = region or get_default_region()
        account_id = auto_detect_account_id(session=session, region=effective_region)
        workflow_manager = WorkflowManager(session=session, region=effective_region, account_id=account_id)
        workflow_info = workflow_manager.get_workflow(name)
        _display_workflow_info(workflow_info, effective_region)
        click.echo()

    except WorkflowError:
        click.echo(
            f"Workflow '{value(name)}' not found. Use {command('act workflow list')} to see available workflows."
        )
        sys.exit(1)
    except Exception as e:
        raise styled_error_exception(message=f"Unexpected error: {str(e)}") from e
