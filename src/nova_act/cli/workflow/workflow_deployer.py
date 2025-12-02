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
"""Workflow deployment orchestration."""

import logging
from pathlib import Path

import click
from boto3 import Session

from nova_act.cli.core.clients.iam import IAMClient
from nova_act.cli.core.config import get_workflow_build_dir
from nova_act.cli.core.identity import extract_role_name_from_arn, validate_iam_role_arn
from nova_act.cli.core.styling import info, success
from nova_act.cli.core.types import WorkflowInfo
from nova_act.cli.workflow.services.agentcore.deployment_service import AgentCoreDeploymentService
from nova_act.cli.workflow.workflow_manager import WorkflowManager


class WorkflowDeployer:
    """Orchestrates workflow deployment across services."""

    def __init__(
        self,
        session: Session | None,
        execution_role_arn: str | None,
        region: str,
        account_id: str,
        workflow_name: str | None = None,
        source_dir: str | None = None,
        entry_point: str | None = None,
        ecr_repo: str | None = None,
        no_build: bool = False,
        skip_entrypoint_validation: bool = False,
        build_dir: str | None = None,
        overwrite_build_dir: bool = False,
        s3_bucket_name: str | None = None,
        skip_s3_creation: bool = False,
    ):
        """Initialize workflow deployer with deployment configuration.

        Args:
            session: boto3 Session for AWS API calls (optional)
            execution_role_arn: IAM role ARN for workflow execution (optional)
            region: AWS region for deployment
            account_id: AWS account ID for deployment
            workflow_name: Name of the workflow to deploy (auto-generated if not provided)
            source_dir: Source code directory path (optional)
            entry_point: Entry point file name within source directory (optional)
            ecr_repo: ECR repository name for container images (optional)
            no_build: Skip container build step if True
            skip_entrypoint_validation: Skip entry point file validation if True
            build_dir: Build output directory path (optional)
            overwrite_build_dir: Overwrite existing build directory if True
            s3_bucket_name: S3 bucket name for deployment artifacts (optional)
            skip_s3_creation: Skip S3 bucket creation if True
        """
        self.session = session
        self.workflow_name = workflow_name
        self.execution_role_arn = execution_role_arn
        self.region = region
        self.account_id = account_id
        self.source_dir = source_dir
        self.entry_point = entry_point
        self.ecr_repo = ecr_repo
        self.no_build = no_build
        self.skip_entrypoint_validation = skip_entrypoint_validation
        self.build_dir = build_dir
        self.overwrite_build_dir = overwrite_build_dir
        self.s3_bucket_name = s3_bucket_name
        self.skip_s3_creation = skip_s3_creation
        self.logger = logging.getLogger(__name__)

    def deploy_workflow(self) -> WorkflowInfo:
        """Deploy workflow using AgentCore service."""
        info("Starting workflow deployment...")
        self._resolve_source_dir_from_entry_point()
        self._validate_execution_role()

        workflow_manager = WorkflowManager(session=self.session, region=self.region, account_id=self.account_id)

        info("Preparing workflow configuration...")
        workflow_name = workflow_manager.ensure_workflow_for_deployment(
            name=self.workflow_name, s3_bucket_name=self.s3_bucket_name, skip_s3_creation=self.skip_s3_creation
        )
        success(f"✓ Workflow '{workflow_name}' ready for deployment")

        # Resolve build directory: use custom if provided, otherwise use state directory
        resolved_build_dir = self.build_dir
        force_overwrite = self.overwrite_build_dir
        if resolved_build_dir is None:
            resolved_build_dir = str(get_workflow_build_dir(workflow_name=workflow_name))
            force_overwrite = True  # Always overwrite state directory builds

        deployment_service = AgentCoreDeploymentService(
            session=self.session,
            agent_name=workflow_name,
            execution_role_arn=self.execution_role_arn,
            region=self.region,
            account_id=self.account_id,
            source_dir=self.source_dir,
            entry_point=self.entry_point,
            ecr_repo=self.ecr_repo,
            no_build=self.no_build,
            skip_entrypoint_validation=self.skip_entrypoint_validation,
            build_dir=resolved_build_dir,
            overwrite_build_dir=force_overwrite,
        )

        agentcore_deployment = deployment_service.deploy_workflow()

        info("Updating deployment state...")
        workflow_manager.update_deployment_state(
            workflow_name=workflow_name,
            agentcore_deployment=agentcore_deployment,
            source_dir=self.source_dir,
            build_dir=resolved_build_dir,
        )
        success("✓ Deployment state updated")

        return workflow_manager.get_workflow(workflow_name)

    def _resolve_source_dir_from_entry_point(self) -> None:
        """Resolve source_dir from entry_point path if source_dir not provided."""
        if self.entry_point and not self.source_dir:
            entry_point_path = Path(self.entry_point).resolve()
            self.source_dir = str(entry_point_path.parent)
            self.entry_point = entry_point_path.name

    def _validate_execution_role(self) -> None:
        """Validate execution role if provided."""
        if not self.execution_role_arn:
            return

        self._validate_execution_role_arn_format(self.execution_role_arn)
        self._validate_execution_role_exists(self.execution_role_arn)

    def _validate_execution_role_arn_format(self, role_arn: str) -> None:
        """Basic IAM role ARN format validation using core identity utilities."""
        if not validate_iam_role_arn(role_arn):
            raise click.BadParameter(
                f"Invalid IAM role ARN format: {role_arn}\n" f"Expected format: arn:aws:iam::123456789012:role/RoleName"
            )

    def _validate_execution_role_exists(self, role_arn: str) -> None:
        """Validate that the provided IAM role exists and is accessible."""
        role_name = extract_role_name_from_arn(role_arn)
        iam_client = IAMClient(session=self.session, region=self.region)

        if not iam_client.role_exists(role_name=role_name):
            raise click.BadParameter(
                f"IAM role does not exist: {role_arn}\n"
                f"Please verify the role ARN is correct and the role exists in your AWS account."
            )
