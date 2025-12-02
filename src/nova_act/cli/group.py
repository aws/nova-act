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
"""Custom Click Group with styled help formatting."""

import click

from nova_act.cli.core.config import get_state_dir
from nova_act.cli.core.styling import header, secondary


class StyledGroup(click.Group):
    """Custom Click Group with styled help formatting."""

    def get_help(self, ctx: click.Context) -> str:
        if ctx.info_name == "workflow":
            return self._get_workflow_help()
        elif ctx.info_name in ("act", "main"):
            return self._get_main_help()
        return super().get_help(ctx)

    def _get_workflow_help(self) -> str:
        deploy_script_cmd = "act workflow deploy --source-dir /path/to/your/script.py"
        run_cmd = 'act workflow run --name quick-deploy-abc123 --payload \'{"input": "data"}\''
        deploy_single_cmd = "act workflow deploy --source-dir ./my_script.py"
        deploy_project_cmd = "act workflow deploy --source-dir ./my_project --entry-point main.py"
        create_cmd = "act workflow create --name my-workflow"
        deploy_named_cmd = "act workflow deploy --name my-workflow --source-dir ./code"
        run_named_cmd = 'act workflow run --name my-workflow --payload \'{"key": "value"}\''
        deploy_region_cmd = "act workflow deploy --name my-workflow --region us-west-2"

        return f"""{header('Usage:')} act workflow [OPTIONS] COMMAND [ARGS]...

{header('Workflow management commands for AWS AgentCore deployment.')}

Manage Python workflows from creation to deployment and execution on AWS AgentCore Runtime.

{header('QUICK START:')}

    # Deploy any Python script directly
    {secondary(deploy_script_cmd)}

    # Run deployed workflow
    {secondary(run_cmd)}

{header('WORKFLOW LIFECYCLE:')}

    {header('1. create')}  - Register workflow in configuration
    {header('2. deploy')}  - Build container and deploy to AWS
    {header('3. run')}     - Execute deployed workflow
    {header('4. list')}    - Show all configured workflows

{header('EXAMPLES:')}

    # Quick deploy a single script
    {secondary(deploy_single_cmd)}

    # Deploy a project directory
    {secondary(deploy_project_cmd)}

    # Create named workflow for reuse
    {secondary(create_cmd)}
    {secondary(deploy_named_cmd)}

    # Execute with JSON payload
    {secondary(run_named_cmd)}

    # Multi-region deployment
    {secondary(deploy_region_cmd)}

{header('Options:')}
  --help  Show this message and exit.

{header('Commands:')}
  create  Register a new workflow in the configuration.
  delete  Delete a workflow from configuration and optionally remove AWS...
  deploy  Deploy workflow to agentcore service with clarified execution...
  list    List all configured workflows.
  run     Execute workflow on AgentCore Runtime.
  show    Show detailed information about a workflow.
  update  Update an existing workflow's WorkflowDefinition ARN for a..."""

    def _get_main_help(self) -> str:
        deploy_cmd = "act workflow deploy --source-dir /path/to/your/code"
        run_cmd = 'act workflow run --name <generated-name> --payload \'{"input": "data"}\''
        help_cmd = "act workflow --help"

        return f"""{header('Usage:')} act [OPTIONS] COMMAND [ARGS]...

{header('Nova Act CLI')} - Deploy Python workflows to AWS AgentCore Runtime.

A streamlined CLI for deploying Python scripts and projects to AWS AgentCore
with automatic containerization, ECR management, and multi-region support.

{header('QUICK START:')}

    # Deploy any Python script in one command
    {secondary(deploy_cmd)}

    # Run the deployed workflow
    {secondary(run_cmd)}

{header('FEATURES:')}

    - {header('Quick deploy')}: Deploy scripts without pre-configuration
    - {header('Auto-containerization')}: Automatic Docker image building
    - {header('ECR management')}: Automatic repository creation and image pushing
    - {header('IAM integration')}: Automatic role creation and management
    - {header('Multi-region')}: Deploy to any AWS region
    - {header('Workflow tracking')}: Persistent configuration management

{header('REQUIREMENTS:')}

    - AWS CLI configured with appropriate permissions
    - Docker installed and running
    - Python 3.10+ environment
    - IAM permissions for ECR, AgentCore, and IAM operations

{header('CONFIGURATION:')}

Workflows are stored in region-specific directories under {secondary(str(get_state_dir()))} with support for
multiple regions and deployment tracking.

For detailed command help, use: {secondary(help_cmd)}

{header('Options:')}
  --version  Show the version and exit.
  --help     Show this message and exit.

{header('Commands:')}
  workflow     Workflow management commands for AWS AgentCore deployment."""
