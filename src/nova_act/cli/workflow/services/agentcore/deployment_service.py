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
from datetime import datetime
from pathlib import Path

from boto3 import Session

from nova_act.cli.core.clients.agentcore.client import AgentCoreClient
from nova_act.cli.core.clients.agentcore.types import AgentRuntimeConfig
from nova_act.cli.core.clients.ecr.client import ECRClient
from nova_act.cli.core.exceptions import DeploymentError
from nova_act.cli.core.logging import log_api_key_status
from nova_act.cli.core.types import AgentCoreDeployment
from nova_act.cli.workflow.services.agentcore.iam_role import AgentCoreRoleCreator
from nova_act.cli.workflow.services.agentcore.image_builder import AgentCoreImageBuilder
from nova_act.cli.workflow.services.agentcore.source_validator import AgentCoreSourceValidator
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
        source_dir: str | None = None,
        entry_point: str | None = None,
        ecr_repo: str | None = None,
        no_build: bool = False,
        skip_entrypoint_validation: bool = False,
        build_dir: str | None = None,
        overwrite_build_dir: bool = False,
    ):
        self.session = session
        self.agent_name = agent_name
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

    def deploy_workflow(self) -> AgentCoreDeployment:
        """Deploy workflow through infrastructure orchestration."""
        if not self.skip_entrypoint_validation:
            self._validate_source_code()

        logger.info("Ensuring IAM execution role...")
        role_arn = self._ensure_execution_role()
        logger.info("Execution role ready")

        logger.info("Building workflow container image...")
        image_tag = self._build_workflow_image()
        logger.info(f"Container image built: {image_tag}")

        logger.info("Pushing image to ECR...")
        image_uri = self._push_image_to_ecr(image_tag)
        logger.info("Image pushed to ECR")

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

    def _build_workflow_image(self) -> str:
        """Build container image or return existing tag."""
        if self.no_build:
            return self._generate_image_tag()

        return self._execute_image_build()

    def _execute_image_build(self) -> str:
        """Execute the actual image building process."""
        workflow_path = self.source_dir or "."
        image_name = self._generate_image_tag()

        if self.entry_point is None:
            raise ValueError("entry_point is required for building workflow image")

        image_builder = AgentCoreImageBuilder(
            image_tag=image_name,
            project_path=workflow_path,
            entry_point=self.entry_point,
            build_dir=Path(self.build_dir) if self.build_dir else None,
            force=self.overwrite_build_dir,
        )
        return image_builder.build_workflow_image()

    def _push_image_to_ecr(self, image_tag: str) -> str:
        """Push image to ECR and return full URI."""
        ecr_client = ECRClient(session=self.session, region=self.region)
        ecr_uri = ecr_client._ensure_default_repository()
        unique_tag = ecr_client.generate_unique_tag(self.agent_name)
        return ecr_client.push_image(local_image_tag=image_tag, ecr_uri=ecr_uri, target_tag=unique_tag)

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
            raise DeploymentError(error_msg)
