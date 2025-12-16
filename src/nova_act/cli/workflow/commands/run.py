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
"""Run command for Nova Act CLI."""

import json
import time
from datetime import datetime, timezone
from typing import Callable

import click
from boto3 import Session
from botocore.exceptions import ClientError, NoCredentialsError, ReadTimeoutError

from nova_act.cli.core.clients.agentcore.client import AgentCoreClient
from nova_act.cli.core.clients.agentcore.constants import DEFAULT_READ_TIMEOUT
from nova_act.cli.core.error_detection import (
    extract_operation_name,
    extract_permission_from_error,
    get_credential_error_message,
    get_permission_error_message,
    is_permission_error,
)
from nova_act.cli.core.exceptions import ConfigurationError, RuntimeError, ValidationError
from nova_act.cli.core.identity import auto_detect_account_id
from nova_act.cli.core.logging import get_follow_command, get_live_tail_command, get_since_command
from nova_act.cli.core.region import get_default_region
from nova_act.cli.core.state_manager import StateManager
from nova_act.cli.core.styling import (
    header,
    secondary,
    styled_error_exception,
    success,
    value,
    warning,
)
from nova_act.cli.workflow.utils.arn import extract_workflow_definition_name_from_arn
from nova_act.cli.workflow.utils.console import build_nova_act_workflow_console_url
from nova_act.cli.workflow.utils.log_tailer import LogEvent, LogTailer


def _handle_credential_error() -> None:
    """Handle AWS credential errors."""
    raise styled_error_exception(get_credential_error_message())


def _handle_client_error(error: ClientError, workflow_name: str, region: str, account_id: str) -> None:
    """Handle AWS ClientError with permission detection."""
    if is_permission_error(error=error):
        operation = extract_operation_name(error=error)
        permission = extract_permission_from_error(error=error)
        message = get_permission_error_message(
            operation=operation,
            workflow_name=workflow_name,
            region=region,
            account_id=account_id,
            permission=permission,
        )
        raise styled_error_exception(message=message)
    raise styled_error_exception(message=f"AWS error during workflow execution: {str(error)}")


def _resolve_payload(payload_file: str, payload: str) -> str:
    """Resolve payload from file or direct input with validation."""
    if not payload_file and not payload:
        raise ValidationError(message="Must provide either --payload-file or --payload")

    if payload_file and payload:
        raise ValidationError(message="Cannot provide both --payload-file and --payload")

    if payload_file:
        try:
            with open(file=payload_file, mode="r") as f:
                content = f.read()
            json.loads(s=content)  # Validate JSON
            return content
        except FileNotFoundError:
            raise ValidationError(message=f"Payload file not found: {payload_file}")
        except PermissionError:
            raise ValidationError(message=f"Cannot read payload file: {payload_file}")
        except json.JSONDecodeError as e:
            raise ValidationError(message=f"Invalid JSON in payload file: {e}")

    return payload


def _get_agent_arn(session: Session, name: str, region: str, account_id: str) -> str:
    """Get agent ARN for workflow from configuration."""
    state_manager = StateManager(account_id=account_id, region=region)
    state = state_manager.get_region_state()

    if name not in state.workflows:
        raise ConfigurationError(f"Workflow '{name}' not found in region '{region}'")

    workflow_info = state.workflows[name]

    if not workflow_info.deployments.agentcore or not workflow_info.deployments.agentcore.deployment_arn:
        raise ConfigurationError(f"Workflow '{name}' not deployed. Run 'act workflow deploy --name {name}' first.")

    return workflow_info.deployments.agentcore.deployment_arn


def _print_execution_logging(name: str, region: str, agent_arn: str, client: AgentCoreClient) -> None:
    """Print logging information and display workflow details."""
    runtime_log_group, otel_log_group = client.get_agent_log_groups(agent_arn)
    live_tail_cmd = get_live_tail_command(runtime_log_group)
    follow_cmd = get_follow_command(runtime_log_group)
    since_cmd = get_since_command(runtime_log_group)

    click.echo(f"\n{header('Workflow Details')}")
    click.echo(f"{secondary('Workflow:')} {value(name)}")
    click.echo(f"{secondary('Agent ARN:')} {value(agent_arn)}")
    click.echo(f"{secondary('Region:')} {value(region)}")

    click.echo(f"\n{header('Logging Information')}")
    click.echo(f"{secondary('Runtime logs:')} {value(runtime_log_group)}")
    click.echo(f"{secondary('OTEL logs:')} {value(otel_log_group)}")

    click.echo(f"\n{secondary('Tail logs with AWS CLI v2:')}")
    click.echo(f"  {secondary(live_tail_cmd)}")
    click.echo(f"  {secondary(follow_cmd)}")
    click.echo(f"  {secondary(since_cmd)}")


def _display_console_link(workflow_definition_arn: str | None, region: str) -> None:
    """Display console deep link to workflow definition."""
    if workflow_definition_arn is None:
        return
    workflow_name = extract_workflow_definition_name_from_arn(workflow_definition_arn)
    console_url = build_nova_act_workflow_console_url(region, workflow_name)
    click.echo(f"🔗 View in console: {value(console_url)}")


def _perform_workflow_execution(
    client: AgentCoreClient, agent_arn: str, payload: str, workflow_definition_arn: str | None, region: str
) -> str:
    """Execute the workflow and return the result."""
    click.echo(f"\n{header('Execution Status')}")
    click.echo(secondary("Starting workflow execution..."))
    warning("⚠ Initial startup may take a few moments")

    response = client.invoke_agent_runtime(agent_arn=agent_arn, payload=payload)
    time.sleep(10)  # Allow remaining logs to be captured by the LogTailer after invoke response
    success("✅ Workflow execution completed successfully!")
    _display_console_link(workflow_definition_arn, region)
    return response


def _execute_workflow(
    session: Session,
    name: str,
    payload: str,
    region: str,
    account_id: str,
    tail_logs: bool = False,
    timeout: int = DEFAULT_READ_TIMEOUT,
) -> str:
    """Execute workflow with AgentCore client."""
    state_manager = StateManager(account_id=account_id, region=region)
    state = state_manager.get_region_state()
    workflow_info = state.workflows.get(name)
    workflow_definition_arn = workflow_info.workflow_definition_arn if workflow_info else None

    agent_arn = _get_agent_arn(session=session, name=name, region=region, account_id=account_id)
    client = AgentCoreClient(session=session, region=region, timeout=timeout)

    _print_execution_logging(name=name, region=region, agent_arn=agent_arn, client=client)

    if tail_logs:
        tailer = _start_log_tailing(session=session, client=client, agent_arn=agent_arn, region=region)
        with tailer:
            result = _perform_workflow_execution(
                client=client,
                agent_arn=agent_arn,
                payload=payload,
                workflow_definition_arn=workflow_definition_arn,
                region=region,
            )
    else:
        result = _perform_workflow_execution(
            client=client,
            agent_arn=agent_arn,
            payload=payload,
            workflow_definition_arn=workflow_definition_arn,
            region=region,
        )

    return result


def _start_log_tailing(session: Session, client: AgentCoreClient, agent_arn: str, region: str) -> LogTailer:
    """Start log tailing for the given agent."""
    runtime_log_group, _ = client.get_agent_log_groups(agent_arn=agent_arn)
    tailer = LogTailer(session=session, region=region, log_group=runtime_log_group)
    tailer.start(callback=_create_log_callback())
    click.echo(f"\n{secondary('📋 Log tailing enabled - showing logs from')} {value(runtime_log_group)}")
    click.echo("─" * 60)
    return tailer


def _create_log_callback() -> Callable[[LogEvent], None]:
    """Create callback function for log events."""

    def log_callback(log_event: LogEvent) -> None:
        timestamp = datetime.fromtimestamp(log_event.timestamp / 1000, tz=timezone.utc)
        time_str = timestamp.strftime("%H:%M:%S")
        click.echo(secondary(f"{time_str} {log_event.message.strip()}"))

    return log_callback


@click.command()
@click.option("--name", "-n", required=True, help="Name of the workflow")
@click.option("--payload-file", type=click.Path(exists=True), help="Path to JSON payload file")
@click.option("--payload", help="JSON payload string")
@click.option("--region", help="AWS region for deployment")
@click.option("--tail-logs", is_flag=True, help="Stream logs in real-time (requires logs:StartLiveTail permission)")
@click.option("--timeout", type=int, default=DEFAULT_READ_TIMEOUT, help="Read timeout in seconds (default: 7200)")
def run(
    *,
    name: str,
    payload_file: str,
    payload: str,
    region: str | None = None,
    tail_logs: bool = False,
    timeout: int = DEFAULT_READ_TIMEOUT,
) -> None:
    """Execute workflow on AgentCore Runtime."""
    try:
        # Create session at command boundary
        session = Session()

        resolved_region = region or get_default_region()
        account_id = auto_detect_account_id(session=session, region=resolved_region)
        resolved_payload = _resolve_payload(payload_file=payload_file, payload=payload)
        _execute_workflow(
            session=session,
            name=name,
            payload=resolved_payload,
            region=resolved_region,
            account_id=account_id,
            tail_logs=tail_logs,
            timeout=timeout,
        )
        click.echo()

    except NoCredentialsError:
        _handle_credential_error()

    except ReadTimeoutError:
        message = (
            f"Read timeout after {timeout} seconds while waiting for AgentCore runtime response.\n\n"
            f"The workflow may still be running in AgentCore. Check the AWS console to view its status.\n\n"
            f"To allow more time for the response, increase the timeout using the --timeout flag:\n"
            f"  act workflow run --name {name} --timeout {timeout * 2}"
        )
        raise styled_error_exception(message=message)

    except ClientError as e:
        _handle_client_error(error=e, workflow_name=name, region=resolved_region, account_id=account_id)

    except (ValidationError, RuntimeError, ConfigurationError) as e:
        raise styled_error_exception(message=str(e))

    except Exception as e:
        raise styled_error_exception(message=f"Unexpected error during workflow execution: {str(e)}") from e
