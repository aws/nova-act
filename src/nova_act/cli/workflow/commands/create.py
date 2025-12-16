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
"""Create command for Nova Act CLI workflows."""

import click
from boto3 import Session
from botocore.exceptions import ClientError, NoCredentialsError

from nova_act.cli.core.config import get_state_file_path
from nova_act.cli.core.error_detection import (
    extract_operation_name,
    extract_permission_from_error,
    get_credential_error_message,
    get_permission_error_message,
    is_permission_error,
)
from nova_act.cli.core.exceptions import ConfigurationError, ValidationError, WorkflowError
from nova_act.cli.core.identity import auto_detect_account_id
from nova_act.cli.core.region import get_default_region
from nova_act.cli.core.styling import (
    command,
    header,
    secondary,
    styled_error_exception,
    success,
    value,
)
from nova_act.cli.workflow.utils.arn import extract_workflow_definition_name_from_arn
from nova_act.cli.workflow.utils.console import build_nova_act_workflow_console_url
from nova_act.cli.workflow.workflow_manager import WorkflowManager


def _handle_credential_error() -> None:
    """Handle AWS credential errors."""
    raise styled_error_exception(get_credential_error_message())


def _handle_client_error(error: ClientError, workflow_name: str, region: str, account_id: str) -> None:
    """Handle AWS ClientError with permission detection."""
    if is_permission_error(error):
        operation = extract_operation_name(error)
        permission = extract_permission_from_error(error)
        message = get_permission_error_message(
            operation=operation,
            workflow_name=workflow_name,
            region=region,
            account_id=account_id,
            permission=permission,
        )
        raise styled_error_exception(message)
    raise styled_error_exception(f"AWS error during workflow creation: {str(error)}")


def _display_creation_success(workflow_definition_arn: str | None, name: str, region: str, account_id: str) -> None:
    """Display workflow creation success message and next steps."""
    success(f"✅ Created workflow '{name}'")
    click.echo(f"   {secondary(text='Region:')} {value(text=region)}")
    click.echo(f"   {secondary(text='WorkflowDefinition ARN:')} {value(text=workflow_definition_arn or 'None')}")
    if workflow_definition_arn:
        workflow_name = extract_workflow_definition_name_from_arn(workflow_definition_arn)
        console_url = build_nova_act_workflow_console_url(region, workflow_name)
        click.echo(f"   {secondary(text='Console URL:')} {value(text=console_url)}")
    click.echo(
        f"   {secondary(text='State saved to:')} "
        f"{value(text=str(get_state_file_path(account_id=account_id, region=region)))}"
    )
    click.echo()
    click.echo(header("Next Steps"))
    click.echo(f"  {command(f'act workflow deploy --name {name} --source-dir <your-code-directory>')}")
    click.echo()


@click.command()
@click.option("--name", "-n", required=True, help="Name of the workflow")
@click.option("--workflow-definition-arn", help="Optional WorkflowDefinition ARN to associate with workflow")
@click.option("--region", help="Region for WorkflowDefinition (defaults to config default_region)")
@click.option("--s3-bucket-name", help="Custom S3 bucket name for workflow exports")
@click.option("--skip-s3-creation", is_flag=True, help="Skip automatic S3 bucket creation")
def create(
    *,
    name: str,
    workflow_definition_arn: str | None = None,
    region: str | None = None,
    s3_bucket_name: str | None = None,
    skip_s3_creation: bool = False,
) -> None:
    """Register a new workflow in the configuration."""
    try:
        # Create session at command boundary
        session = Session()

        effective_region = region or get_default_region()
        account_id = auto_detect_account_id(session=session, region=effective_region)
        workflow_manager = WorkflowManager(session=session, region=effective_region, account_id=account_id)

        workflow = workflow_manager.create_workflow_with_definition(
            name=name,
            workflow_definition_arn=workflow_definition_arn,
            s3_bucket_name=s3_bucket_name,
            skip_s3_creation=skip_s3_creation,
        )

        _display_creation_success(
            workflow_definition_arn=workflow.workflow_definition_arn,
            name=workflow.name,
            region=effective_region,
            account_id=account_id,
        )

    except NoCredentialsError:
        _handle_credential_error()

    except ClientError as e:
        _handle_client_error(error=e, workflow_name=name, region=effective_region, account_id=account_id)

    except (WorkflowError, ValidationError, ConfigurationError) as e:
        raise styled_error_exception(str(e))

    except Exception as e:
        raise styled_error_exception(f"Unexpected error during workflow creation: {str(e)}") from e
