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
"""
WorkflowManager class for workflow lifecycle management and CRUD operations.

Handles all workflow operations including read, write, create, update, and delete.
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from boto3 import Session
from botocore.exceptions import ClientError

from nova_act.cli.core.clients.nova_act.client import NovaActClient
from nova_act.cli.core.clients.nova_act.types import (
    CreateWorkflowDefinitionRequest,
    ExportConfig,
    GetWorkflowDefinitionRequest,
)
from nova_act.cli.core.clients.s3.client import S3Client
from nova_act.cli.core.error_detection import get_workflow_not_found_message
from nova_act.cli.core.exceptions import (
    ValidationError,
    WorkflowError,
    WorkflowNameArnMismatchError,
)
from nova_act.cli.core.state_manager import StateManager
from nova_act.cli.core.styling import info, success
from nova_act.cli.core.types import AgentCoreDeployment, WorkflowInfo
from nova_act.cli.workflow.utils.arn import construct_workflow_definition_arn
from nova_act.cli.workflow.utils.bucket_manager import BucketManager

logger = logging.getLogger(__name__)


class WorkflowManager:
    """Workflow lifecycle management and CRUD operations."""

    def __init__(self, session: Session | None, region: str, account_id: str):
        """Initialize WorkflowManager with region and account ID."""
        self.session = session or Session()
        self.region = region
        self.account_id = account_id
        self.state_manager = StateManager(account_id=self.account_id, region=self.region)

    def list_workflows(self) -> Dict[str, WorkflowInfo]:
        """Get workflows for the current account and region."""
        state = self.state_manager.get_region_state()
        return state.workflows

    def get_workflow(self, name: str) -> WorkflowInfo:
        """Get workflow information by name from current account and region."""
        self._validate_workflow_exists(name)
        state = self.state_manager.get_region_state()
        return state.workflows[name]

    def _check_workflow_exists(self, name: str) -> bool:
        """Check if workflow exists without raising exception."""
        state = self.state_manager.get_region_state()
        return name in state.workflows

    def _validate_workflow_exists(self, name: str) -> None:
        """Validate workflow exists using internal state manager."""
        state = self.state_manager.get_region_state()
        if name not in state.workflows:
            available = list(state.workflows.keys())
            message = get_workflow_not_found_message(
                name=name, region=self.region, account_id=self.account_id, available_workflows=available
            )
            raise WorkflowError(message)

    def create_workflow_with_definition(
        self,
        name: str,
        workflow_definition_arn: str | None = None,
        s3_bucket_name: str | None = None,
        skip_s3_creation: bool = False,
    ) -> WorkflowInfo:
        """Create workflow with WorkflowDefinition, handling all ARN resolution logic."""
        validate_workflow_name(name)

        if self._check_workflow_exists(name=name):
            logger.info(f"Workflow '{name}' already exists, checking WorkflowDefinition")
            workflow = self.get_workflow(name=name)
            return self._recover_workflow_definition_if_needed(
                workflow=workflow, s3_bucket_name=s3_bucket_name, skip_s3_creation=skip_s3_creation
            )

        if workflow_definition_arn is None:
            resolved_arn = self._ensure_workflow_definition_exists(
                name=name, s3_bucket_name=s3_bucket_name, skip_s3_creation=skip_s3_creation
            )
        else:
            self._validate_workflow_name_matches_arn(
                workflow_name=name, workflow_definition_arn=workflow_definition_arn
            )
            self._validate_workflow_definition_exists(workflow_definition_arn=workflow_definition_arn)
            resolved_arn = workflow_definition_arn

        return self._save_workflow_to_state(name=name, workflow_definition_arn=resolved_arn)

    def _ensure_workflow_definition_exists(
        self, name: str, s3_bucket_name: str | None, skip_s3_creation: bool
    ) -> str | None:
        """Ensure WorkflowDefinition exists in AWS, creating if missing.

        Idempotent operation that attempts to create WorkflowDefinition and handles
        ConflictException by constructing ARN from name.

        Args:
            name: Workflow name
            s3_bucket_name: Optional S3 bucket for exports
            skip_s3_creation: Skip S3 bucket creation

        Returns:
            WorkflowDefinition ARN if successful, None if creation fails
        """
        try:
            return self.create_workflow_definition(
                name=name,
                description="Workflow created via CLI",
                s3_bucket_name=s3_bucket_name,
                skip_s3_creation=skip_s3_creation,
            )
        except Exception as e:
            if isinstance(e, ClientError) and e.response.get("Error", {}).get("Code") == "ConflictException":
                logger.info(f"WorkflowDefinition '{name}' already exists in AWS")
                return construct_workflow_definition_arn(name=name, region=self.region, account_id=self.account_id)
            else:
                logger.warning(f"Could not create WorkflowDefinition: {e}")
                return None

    def _recover_workflow_definition_if_needed(
        self, workflow: WorkflowInfo, s3_bucket_name: str | None, skip_s3_creation: bool
    ) -> WorkflowInfo:
        """Recover missing WorkflowDefinition ARN if needed.

        Checks if workflow has None ARN and attempts recovery by creating
        WorkflowDefinition in AWS. Updates workflow state if successful.

        Args:
            workflow: Workflow to check and recover
            s3_bucket_name: Optional S3 bucket for exports
            skip_s3_creation: Skip S3 bucket creation

        Returns:
            Updated workflow with ARN if recovery successful, original workflow otherwise
        """
        if workflow.workflow_definition_arn is not None:
            return workflow

        logger.info(f"Workflow '{workflow.name}' missing WorkflowDefinition, attempting recovery")
        resolved_arn = self._ensure_workflow_definition_exists(
            name=workflow.name, s3_bucket_name=s3_bucket_name, skip_s3_creation=skip_s3_creation
        )

        if resolved_arn:
            workflow.workflow_definition_arn = resolved_arn
            state = self.state_manager.get_region_state()
            state.workflows[workflow.name] = workflow
            self.state_manager.save_region_state(state)

        return workflow

    def create_workflow(self, name: str, workflow_definition_arn: str | None = None) -> WorkflowInfo:
        """Create a new workflow without directory binding."""
        validate_workflow_name(name=name)

        if workflow_definition_arn is not None:
            self._validate_workflow_name_matches_arn(
                workflow_name=name, workflow_definition_arn=workflow_definition_arn
            )
            self._validate_workflow_definition_exists(workflow_definition_arn=workflow_definition_arn)
        else:
            workflow_definition_arn = construct_workflow_definition_arn(
                name=name, region=self.region, account_id=self.account_id
            )

        return self._save_workflow_to_state(name=name, workflow_definition_arn=workflow_definition_arn)

    def _save_workflow_to_state(self, name: str, workflow_definition_arn: str | None = None) -> WorkflowInfo:
        """Save workflow to state management with proper initialization."""
        workflow_info = WorkflowInfo(
            name=name,
            directory_path="",  # No directory binding at creation
            created_at=datetime.now(timezone.utc),
            workflow_definition_arn=workflow_definition_arn,
        )

        state = self.state_manager.get_region_state()
        state.workflows[name] = workflow_info
        self.state_manager.save_region_state(state)

        logger.info(f"Created workflow '{name}' in account '{self.account_id}', region '{self.region}'")
        return workflow_info

    def update_workflow_definition_arn(self, name: str, workflow_definition_arn: str) -> WorkflowInfo:
        """Update workflow's WorkflowDefinition ARN in current account."""
        self._validate_workflow_exists(name=name)
        self._validate_workflow_name_matches_arn(workflow_name=name, workflow_definition_arn=workflow_definition_arn)
        self._validate_workflow_definition_exists(workflow_definition_arn=workflow_definition_arn)

        state = self.state_manager.get_region_state()
        workflow = state.workflows[name]
        workflow.workflow_definition_arn = workflow_definition_arn
        self.state_manager.save_region_state(state)

        logger.info(f"Updated workflow '{name}' ARN in account '{self.account_id}', region '{self.region}'")
        return workflow

    def _extract_resource_name_from_arn(self, arn: str) -> str:
        """Extract resource name from WorkflowDefinition ARN.

        Expected format: arn:aws:nova-act:region:account:workflow-definition/resource-name
        """
        if not arn or not isinstance(arn, str):
            raise ValidationError(f"Invalid ARN format: {arn}")

        parts = arn.split(":")
        if len(parts) != 6 or parts[0] != "arn" or parts[1] != "aws":
            raise ValidationError(f"Invalid ARN format: {arn}")

        resource_part = parts[5]  # workflow-definition/resource-name
        if "/" not in resource_part:
            raise ValidationError(f"Invalid ARN format: {arn}")

        try:
            return resource_part.split("/")[-1]
        except (IndexError, AttributeError):
            raise ValidationError(message=f"Invalid ARN format: {arn}")

    def _validate_workflow_name_matches_arn(self, workflow_name: str, workflow_definition_arn: str) -> None:
        """Validate that workflow name matches the resource name in the ARN.

        This prevents workflow name drift from the actual AWS resource.
        """
        resource_name = self._extract_resource_name_from_arn(workflow_definition_arn)
        if workflow_name != resource_name:
            raise WorkflowNameArnMismatchError(
                f"Workflow name '{workflow_name}' does not match ARN resource name '{resource_name}'. "
                f"This would cause drift between local configuration and AWS resources. "
                f"Please ensure the workflow name matches the WorkflowDefinition resource name."
            )

    def _validate_workflow_definition_exists(self, workflow_definition_arn: str) -> None:
        """Validate that WorkflowDefinition exists in AWS before state changes."""
        info("Validating workflow definition in AWS...")
        client = NovaActClient(self.session, region_name=self.region)

        try:
            # Extract workflow definition name from ARN
            workflow_name = self._extract_resource_name_from_arn(arn=workflow_definition_arn)
            request = GetWorkflowDefinitionRequest(workflowDefinitionName=workflow_name)
            client.get_workflow_definition(request=request)
            logger.info(f"Validated WorkflowDefinition exists: {workflow_definition_arn}")
            success("✓ Workflow definition validated")
        except Exception as e:
            raise WorkflowError(f"WorkflowDefinition {workflow_definition_arn} does not exist in AWS: {e}")

    def delete_workflow(self, name: str) -> None:
        """Delete workflow from current account and region."""
        self._validate_workflow_exists(name)

        state = self.state_manager.get_region_state()
        del state.workflows[name]
        self.state_manager.save_region_state(state)

        logger.info(f"Deleted workflow '{name}' from account '{self.account_id}', region '{self.region}'")

    def ensure_workflow_for_deployment(
        self, name: str | None, s3_bucket_name: str | None, skip_s3_creation: bool
    ) -> str:
        """Ensure workflow exists for deployment, creating temporary one if needed."""
        workflow_name = name or f"workflow-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        if not name:
            self._register_temporary_workflow(
                workflow_name=workflow_name, s3_bucket_name=s3_bucket_name, skip_s3_creation=skip_s3_creation
            )
        else:
            self._validate_workflow_exists(name=workflow_name)

        return workflow_name

    def update_deployment_state(
        self,
        workflow_name: str,
        agentcore_deployment: AgentCoreDeployment,
        source_dir: str | None = None,
        build_dir: str | None = None,
    ) -> None:
        """Update workflow state with deployment results."""
        state = self.state_manager.get_region_state()

        if workflow_name not in state.workflows:
            logger.warning(f"Workflow '{workflow_name}' not found during deployment state update")
            return

        workflow = state.workflows[workflow_name]
        workflow.deployments.agentcore = agentcore_deployment
        workflow.last_image_tag = agentcore_deployment.image_tag

        # Update directory path: prefer build_dir, fallback to source_dir
        if build_dir:
            workflow.directory_path = str(Path(build_dir).resolve())
        elif source_dir:
            workflow.directory_path = str(Path(source_dir).resolve())

        self.state_manager.save_region_state(state)

        logger.info(
            f"Updated deployment state for '{workflow_name}' in account '{self.account_id}', region '{self.region}'"
        )

    def create_workflow_definition(
        self,
        name: str,
        description: str | None = None,
        s3_bucket_name: str | None = None,
        skip_s3_creation: bool = False,
    ) -> str:
        """Create a workflow definition using AWS nova-act service."""
        info(f"Creating workflow definition '{name}'...")
        client = NovaActClient(self.session, region_name=self.region)

        # Create export config unless explicitly skipped
        export_config = None
        if not skip_s3_creation:
            export_config = self._create_export_config(custom_bucket_name=s3_bucket_name)

        request = CreateWorkflowDefinitionRequest(name=name, description=description, exportConfig=export_config)
        response = client.create_workflow_definition(request=request)
        success("✓ Workflow definition created")
        return getattr(
            response,
            "arn",
            construct_workflow_definition_arn(name=name, region=self.region, account_id=self.account_id),
        )

    def _create_export_config(self, custom_bucket_name: str | None = None) -> ExportConfig | None:
        """Create export config with S3 bucket."""
        try:
            if custom_bucket_name:
                info(f"Checking S3 bucket '{custom_bucket_name}'...")
                # Validate custom bucket exists
                s3_client = S3Client(session=self.session, region=self.region)
                if s3_client.bucket_exists(bucket_name=custom_bucket_name):
                    logger.info(f"Skipping creating existing custom S3 bucket: " f"{custom_bucket_name}")
                    success("✓ Using existing S3 bucket")
                    return ExportConfig(s3BucketName=custom_bucket_name)
                else:
                    logger.warning(f"Custom bucket {custom_bucket_name} not found, " f"creating default")

            info("Setting up S3 bucket for workflow exports...")
            bucket_manager = BucketManager(session=self.session, region=self.region, account_id=self.account_id)
            bucket_name = bucket_manager.ensure_default_bucket()

            if bucket_name:
                success(f"✓ S3 bucket ready: {bucket_name}")
                return ExportConfig(s3BucketName=bucket_name)

            raise RuntimeError("Failed to create S3 bucket")
        except Exception as e:
            logger.error(f"Failed to create export config: {e}")
            raise

    def _register_temporary_workflow(
        self, workflow_name: str, s3_bucket_name: str | None, skip_s3_creation: bool
    ) -> None:
        """Register temporary workflow for quick-deploy."""
        if not skip_s3_creation:
            self._create_workflow_with_s3(workflow_name=workflow_name, s3_bucket_name=s3_bucket_name)
        else:
            self.create_workflow(name=workflow_name)

    def _create_workflow_with_s3(self, workflow_name: str, s3_bucket_name: str | None) -> None:
        """Create workflow definition with S3 bucket."""
        workflow_definition_arn = self._ensure_workflow_definition_exists(
            name=workflow_name, s3_bucket_name=s3_bucket_name, skip_s3_creation=False
        )
        self.create_workflow(name=workflow_name, workflow_definition_arn=workflow_definition_arn)


def validate_workflow_name(name: str) -> None:
    """Validate workflow name format and constraints."""
    if not name:
        raise ValidationError("Workflow name cannot be empty")

    if len(name) > 64:
        raise ValidationError("Workflow name cannot exceed 64 characters")

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9\-]*$", name):
        raise ValidationError("Workflow name must start with a letter and contain only letters, numbers, and hyphens")

    if "--" in name:
        raise ValidationError("Workflow name cannot contain consecutive hyphens")

    if name.endswith("-"):
        raise ValidationError("Workflow name cannot end with a hyphen")
