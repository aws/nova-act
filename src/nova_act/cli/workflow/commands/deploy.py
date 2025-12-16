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
"""Deploy command for Nova Act CLI."""

import subprocess
import tempfile

import click
from boto3 import Session
from botocore.exceptions import ClientError, NoCredentialsError

from nova_act.cli.core.constants import BUILD_DIR_PREFIX, DEFAULT_ENTRY_POINT
from nova_act.cli.core.error_detection import (
    extract_operation_name,
    extract_permission_from_error,
    get_credential_error_message,
    get_docker_build_failed_message,
    get_docker_not_running_message,
    get_permission_error_message,
    is_docker_running,
    is_permission_error,
)
from nova_act.cli.core.exceptions import ConfigurationError, DeploymentError, ValidationError
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
from nova_act.cli.core.types import WorkflowInfo
from nova_act.cli.workflow.utils.arn import (
    extract_agent_id_from_arn,
    extract_workflow_definition_name_from_arn,
)
from nova_act.cli.workflow.utils.console import (
    build_bedrock_agentcore_console_url,
    build_nova_act_workflow_console_url,
)
from nova_act.cli.workflow.workflow_deployer import WorkflowDeployer


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
    raise styled_error_exception(f"AWS error during deployment: {str(error)}")


def _handle_docker_error(build_dir: str | None) -> None:
    """Handle Docker build errors."""
    if not is_docker_running():
        raise styled_error_exception(get_docker_not_running_message())

    build_path = build_dir or f"{tempfile.gettempdir()}/{BUILD_DIR_PREFIX}*/"
    raise styled_error_exception(get_docker_build_failed_message(build_path=build_path))


@click.command()
@click.option("--name", "-n", help="Name of the workflow (auto-generated if using --source-dir)")
@click.option("--source-dir", help="Path to source directory for quick-deploy")
@click.option("--entry-point", help="Entry point script file (e.g., 'my_script.py')")
@click.option("--region", help="AWS region for deployment")
@click.option("--execution-role-arn", help="Use existing IAM role ARN for workflow execution")
@click.option(
    "--ecr-repo", help="Custom ECR repository URI (e.g., 123456789012.dkr.ecr.us-east-1.amazonaws.com/my-repo)"
)
@click.option("--no-build", is_flag=True, help="Skip building before deploy")
@click.option("--skip-entrypoint-validation", is_flag=True, help="Skip entry point validation (advanced users only)")
@click.option("--build-dir", help="Custom local directory in which deployment build files will be written")
@click.option("--overwrite-build-dir", is_flag=True, help="Overwrite existing build directory without prompting")
@click.option("--s3-bucket-name", help="Custom S3 bucket name for workflow exports")
@click.option("--skip-s3-creation", is_flag=True, help="Skip automatic S3 bucket creation")
def deploy(
    name: str | None,
    source_dir: str | None,
    entry_point: str | None,
    region: str | None,
    execution_role_arn: str | None,
    ecr_repo: str | None,
    no_build: bool,
    skip_entrypoint_validation: bool,
    build_dir: str | None,
    overwrite_build_dir: bool,
    s3_bucket_name: str | None,
    skip_s3_creation: bool,
) -> None:
    """Deploy workflow to agentcore service."""
    try:
        # Create session at command boundary
        session = Session()

        # Resolve region and account_id
        effective_region = region or get_default_region()
        effective_account_id = auto_detect_account_id(session=session, region=effective_region)

        # Use default entry_point if none provided
        effective_entry_point = entry_point or DEFAULT_ENTRY_POINT

        # Deploy workflow using domain service
        deployer = WorkflowDeployer(
            session=session,
            execution_role_arn=execution_role_arn,
            region=effective_region,
            account_id=effective_account_id,
            workflow_name=name,
            source_dir=source_dir,
            entry_point=effective_entry_point,
            ecr_repo=ecr_repo,
            no_build=no_build,
            skip_entrypoint_validation=skip_entrypoint_validation,
            build_dir=build_dir,
            overwrite_build_dir=overwrite_build_dir,
            s3_bucket_name=s3_bucket_name,
            skip_s3_creation=skip_s3_creation,
        )
        workflow_info = deployer.deploy_workflow()

        # Display results
        _display_deployment_results(workflow_info=workflow_info, region=effective_region)

    except NoCredentialsError:
        _handle_credential_error()

    except ClientError as e:
        _handle_client_error(
            error=e, workflow_name=name or "unnamed", region=effective_region, account_id=effective_account_id
        )

    except subprocess.CalledProcessError:
        _handle_docker_error(build_dir=build_dir)

    except (ConfigurationError, DeploymentError, ValidationError) as e:
        raise styled_error_exception(str(e))

    except Exception as e:
        raise styled_error_exception(f"Unexpected error during deployment: {str(e)}") from e


def _display_deployment_results(workflow_info: WorkflowInfo, region: str) -> None:
    """Display deployment results with styling and next steps."""
    click.echo()
    click.echo()
    success("🚀 Deployment successful!")
    click.echo()
    click.echo(header("Deployment Details:"))
    click.echo(f"  {secondary('Name:')}       {value(workflow_info.name)}")

    agent_arn = workflow_info.deployments.agentcore.deployment_arn if workflow_info.deployments.agentcore else None
    click.echo(f"  {secondary('Agent ARN:')}  {value(agent_arn or 'Not available')}")
    click.echo(f"  {secondary('Region:')}     {value(region)}")

    if workflow_info.workflow_definition_arn:
        workflow_name = extract_workflow_definition_name_from_arn(workflow_info.workflow_definition_arn)
        workflow_console_url = build_nova_act_workflow_console_url(region, workflow_name)
        click.echo(f"  {secondary('Workflow Console:')} {value(workflow_console_url)}")

    if agent_arn:
        agent_id = extract_agent_id_from_arn(agent_arn=agent_arn)
        agent_console_url = build_bedrock_agentcore_console_url(region=region, agent_id=agent_id)
        click.echo(f"  {secondary('Agent Console:')}    {value(agent_console_url)}")

    click.echo()
    click.echo(header("Next Steps:"))
    empty_payload = '"{}"'
    click.echo(f"  {secondary('Run workflow:')}")
    click.echo(f"    {command(f'act workflow run --name {workflow_info.name} --payload {empty_payload}')}")
    click.echo(f"  {secondary('Run with logs:')}")
    click.echo(f"    {command(f'act workflow run --name {workflow_info.name} --payload {empty_payload} --tail-logs')}")
    click.echo()
