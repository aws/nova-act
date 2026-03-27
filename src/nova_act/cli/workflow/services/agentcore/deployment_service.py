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
"""AgentCore deployment service for workflow infrastructure orchestration."""

import logging
import shutil
from datetime import datetime
from pathlib import Path

from boto3 import Session

from nova_act.cli.core.clients.agentcore.client import AgentCoreClient
from nova_act.cli.core.clients.agentcore.types import AgentRuntimeConfig
from nova_act.cli.core.constants import BUILD_DIR_PREFIX
from nova_act.cli.core.exceptions import DeploymentError
from nova_act.cli.core.logging import log_api_key_status
from nova_act.cli.core.types import AgentCoreDeployment
from nova_act.cli.workflow.services.agentcore.iam_role import AgentCoreRoleCreator
from nova_act.cli.workflow.services.agentcore.image_builder import BuildContextPreparer
from nova_act.cli.workflow.services.agentcore.source_validator import AgentCoreSourceValidator
from nova_act.cli.workflow.utils.build_strategy import ImageBuilder
from nova_act.cli.workflow.utils.tags import generate_workflow_tags

logger = logging.getLogger(__name__)


class AgentCoreDeploymentService:
    """Orchestrates AgentCore workflow deployment infrastructure operations."""

    def __init__(
        self,
        session: Session | None,
        agent_name: str,
        execution_role_arn: str | None,
        region: str,
        account_id: str,
        image_builder: ImageBuilder,
        source_dir: str | None = None,
        entry_point: str | None = None,
        ecr_repo: str | None = None,
        skip_entrypoint_validation: bool = False,
        build_dir: str | None = None,
        overwrite_build_dir: bool = False,
    ):
        self.session = session
        self.agent_name = agent_name
        self.execution_role_arn = execution_role_arn
        self.region = region
        self.account_id = account_id
        self.image_builder = image_builder
        self.source_dir = source_dir
        self.entry_point = entry_point
        self.ecr_repo = ecr_repo
        self.skip_entrypoint_validation = skip_entrypoint_validation
        self.build_dir = build_dir
        self.overwrite_build_dir = overwrite_build_dir

    def deploy_workflow(self) -> AgentCoreDeployment:
        """Deploy workflow through infrastructure orchestration."""
        if not self.skip_entrypoint_validation:
            self._validate_source_code()

        logger.info("Ensuring IAM execution role...")
        role_arn = self._ensure_execution_role()
        logger.info("Execution role ready")

        logger.info("Building and pushing workflow container image...")
        image_tag, image_uri = self._build_and_push_image()
        logger.info(f"Image ready: {image_uri}")

        logger.info("Creating AgentCore runtime...")
        agent_arn = self._create_agentcore_runtime(image_uri=image_uri, role_arn=role_arn)
        logger.info("AgentCore runtime created")

        return AgentCoreDeployment(deployment_arn=agent_arn, image_uri=image_uri, image_tag=image_tag)

    def _validate_source_code(self) -> None:
        """Validate source code and entry point."""
        validator = AgentCoreSourceValidator(
            source_dir=self.source_dir or ".",
            entry_point=self.entry_point,
            skip_validation=self.skip_entrypoint_validation,
        )
        validator.validate()

    def _build_and_push_image(self) -> tuple[str, str]:
        """Build and push container image using the configured strategy.

        Returns:
            Tuple of (image_tag, image_uri).
        """
        image_tag = self._generate_image_tag()

        if self.entry_point is None:
            raise ValueError("entry_point is required for building workflow image")

        workflow_path = self.source_dir or "."

        # Prepare build context (AgentCore-specific: Dockerfile template processing)
        context_builder = BuildContextPreparer(
            image_tag=image_tag,
            project_path=workflow_path,
            entry_point=self.entry_point,
            region=self.region,
            build_dir=Path(self.build_dir) if self.build_dir else None,
            force=self.overwrite_build_dir,
        )
        build_dir = context_builder.prepare_build_context()

        try:
            # Build and push via strategy
            result = self.image_builder.build_and_push(
                build_dir=build_dir, image_tag=image_tag, agent_name=self.agent_name
            )
            return image_tag, result.image_uri
        finally:
            # Cleanup temp build dir if we created it
            if not self.build_dir and build_dir and BUILD_DIR_PREFIX in build_dir.name:
                logger.info(f"Cleaning up temporary build directory: {build_dir}")
                shutil.rmtree(build_dir, ignore_errors=True)

    def _create_agentcore_runtime(self, image_uri: str, role_arn: str) -> str:
        """Create AgentCore runtime with configuration."""
        agentcore_client = AgentCoreClient(session=self.session, region=self.region)
        log_api_key_status(logger)
        tags = generate_workflow_tags(self.agent_name)

        config = AgentRuntimeConfig(
            container_uri=image_uri,
            role_arn=role_arn,
            environment_variables={},
            tags=tags,
        )
        return agentcore_client.create_agent_runtime(name=self.agent_name, config=config)

    def _generate_image_tag(self) -> str:
        """Generate workflow-specific image tag."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"{self.agent_name}-{timestamp}"

    def _ensure_execution_role(self) -> str:
        """Resolve IAM execution role with clear error handling."""
        if self.execution_role_arn:
            logger.info(f"Using provided execution role: {self.execution_role_arn}")
            return self.execution_role_arn

        logger.info(f"Auto-creating execution role for workflow: {self.agent_name}")
        try:
            role_creator = AgentCoreRoleCreator(session=self.session, account_id=self.account_id, region=self.region)
            return role_creator.create_default_execution_role(self.agent_name)
        except Exception as e:
            error_msg = (
                f"Failed to auto-create execution role: {str(e)}\n\n"
                f"To resolve this issue, you can either:\n"
                f"1. Provide an existing role: --execution-role-arn arn:aws:iam::ACCOUNT:role/ROLE_NAME\n"
                f"2. Use a role/user with IAM permissions to create roles (iam:CreateRole, iam:AttachRolePolicy)\n"
                f"3. Ask your administrator to create the role and provide the ARN"
            )
            raise DeploymentError(error_msg) from e
