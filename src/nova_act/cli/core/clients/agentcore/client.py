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
"""AgentCore client for workflow operations."""

import json
import logging
import re
import uuid
from typing import Tuple

from boto3 import Session
from botocore.config import Config
from botocore.exceptions import ClientError

from nova_act.cli.core.clients.agentcore.constants import (
    AGENT_NAME_PREFIX,
    ALREADY_EXISTS_ERROR,
    BEDROCK_AGENT_CONTROL_SERVICE,
    BEDROCK_AGENT_DATA_SERVICE,
    CONFLICT_ERROR,
    DEFAULT_ENDPOINT_NAME,
    DEFAULT_READ_TIMEOUT,
    LOG_GROUP_PREFIX,
    MAX_AGENT_NAME_LENGTH,
    OTEL_LOG_SUFFIX,
    PUBLIC_NETWORK_MODE,
)
from nova_act.cli.core.clients.agentcore.response_parser import (
    parse_invoke_response,
)
from nova_act.cli.core.clients.agentcore.types import (
    AgentRuntimeArtifact,
    AgentRuntimeConfig,
    AgentRuntimeSummary,
    ContainerConfiguration,
    CreateAgentRuntimeRequest,
    CreateAgentRuntimeResponse,
    InvokeAgentRuntimeRequest,
    InvokeAgentRuntimeResponse,
    ListAgentRuntimesRequest,
    ListAgentRuntimesResponse,
    UpdateAgentRuntimeRequest,
    UpdateAgentRuntimeResponse,
)
from nova_act.cli.core.exceptions import (
    DeploymentError,
    ValidationError,
)

logger = logging.getLogger(__name__)


class AgentCoreClient:
    """Client for AgentCore service operations."""

    def __init__(self, session: Session | None, region: str, timeout: int = DEFAULT_READ_TIMEOUT):
        self.region = region
        self.session = session or Session()
        config = Config(read_timeout=timeout, retries={"max_attempts": 1})
        self.control_client = self.session.client(
            BEDROCK_AGENT_CONTROL_SERVICE, region_name=region, config=config
        )  # type: ignore[call-overload]
        self.data_client = self.session.client(
            BEDROCK_AGENT_DATA_SERVICE, region_name=region, config=config
        )  # type: ignore[call-overload]

    def invoke_agent_runtime(self, agent_arn: str, payload: str) -> str:
        """Execute workflow on AgentCore Runtime."""
        self._validate_json_payload(payload)
        session_id = str(uuid.uuid4())
        logger.info(f"Invoking {agent_arn}...")

        response = self._invoke_agent_runtime(agent_arn=agent_arn, session_id=session_id, payload=payload)
        parsed_response = parse_invoke_response(response.model_dump())
        return parsed_response["response"]

    def _invoke_agent_runtime(self, agent_arn: str, session_id: str, payload: str) -> InvokeAgentRuntimeResponse:
        """Invoke agent runtime with given parameters."""
        request = InvokeAgentRuntimeRequest(agentRuntimeArn=agent_arn, runtimeSessionId=session_id, payload=payload)
        response = self.data_client.invoke_agent_runtime(**request.model_dump())
        return InvokeAgentRuntimeResponse(response=response)

    def update_agent_runtime(self, agent_id: str, config: AgentRuntimeConfig) -> str:
        """Update existing AgentCore Runtime."""
        request = self._build_update_request(agent_id=agent_id, config=config)
        response = self.control_client.update_agent_runtime(**request.model_dump())
        typed_response = UpdateAgentRuntimeResponse(**response)
        return typed_response.agentRuntimeArn

    def _build_update_request(self, agent_id: str, config: AgentRuntimeConfig) -> UpdateAgentRuntimeRequest:
        """Build request parameters for update operation."""
        artifact = AgentRuntimeArtifact(
            containerConfiguration=ContainerConfiguration(containerUri=config.container_uri)
        )
        return UpdateAgentRuntimeRequest(
            agentRuntimeId=agent_id,
            agentRuntimeArtifact=artifact,
            roleArn=config.role_arn,
            networkConfiguration={"networkMode": PUBLIC_NETWORK_MODE},
            environmentVariables=config.environment_variables,
        )

    def _sanitize_name(self, name: str) -> str:
        """Sanitize name to match AWS AgentCore requirements: [a-zA-Z][a-zA-Z0-9_]{0,47}."""
        original_name = name

        # Ensure starts with letter
        if not name[0].isalpha():
            name = AGENT_NAME_PREFIX + name

        # Replace invalid characters with underscores
        sanitized = re.sub(pattern=r"[^a-zA-Z0-9_]", repl="_", string=name)

        # Truncate to maximum length
        if len(sanitized) > MAX_AGENT_NAME_LENGTH:
            sanitized = sanitized[:MAX_AGENT_NAME_LENGTH]

        if sanitized != original_name:
            logger.warning(f"Agent name sanitized for AgentCore: '{original_name}' -> '{sanitized}'")

        return sanitized

    def _create_new_agent_runtime(self, sanitized_name: str, config: AgentRuntimeConfig) -> str:
        """Create new agent runtime."""
        request = self._build_create_request(sanitized_name=sanitized_name, config=config)
        response = self.control_client.create_agent_runtime(**request.model_dump())
        typed_response = CreateAgentRuntimeResponse(**response)
        return typed_response.agentRuntimeArn

    def _build_create_request(self, sanitized_name: str, config: AgentRuntimeConfig) -> CreateAgentRuntimeRequest:
        """Build request parameters for create operation."""
        artifact = AgentRuntimeArtifact(
            containerConfiguration=ContainerConfiguration(containerUri=config.container_uri)
        )
        return CreateAgentRuntimeRequest(
            agentRuntimeName=sanitized_name,
            agentRuntimeArtifact=artifact,
            roleArn=config.role_arn,
            networkConfiguration={"networkMode": PUBLIC_NETWORK_MODE},
            environmentVariables=config.environment_variables,
            tags=config.tags,
        )

    def create_agent_runtime(self, name: str, config: AgentRuntimeConfig) -> str:
        """Create or update AgentCore Runtime."""
        self._validate_runtime_config(config)
        sanitized_name = self._sanitize_name(name)

        try:
            logger.info(f"Creating agent runtime: {sanitized_name}")
            return self._create_new_agent_runtime(sanitized_name=sanitized_name, config=config)
        except ClientError as e:
            return self._handle_create_conflict(error=e, sanitized_name=sanitized_name, config=config)

    def _validate_runtime_config(self, config: AgentRuntimeConfig) -> None:
        """Validate runtime configuration before creation."""
        if not config.role_arn:
            raise DeploymentError(f"No role ARN provided for region {self.region}")

    def _handle_create_conflict(self, error: ClientError, sanitized_name: str, config: AgentRuntimeConfig) -> str:
        """Handle conflict when creating agent runtime."""
        if self._is_already_exists_error(error):
            return self._update_existing_runtime(sanitized_name=sanitized_name, config=config)
        raise DeploymentError(f"Failed to create agent runtime: {str(error)}")

    def _is_already_exists_error(self, error: ClientError) -> bool:
        """Check if error indicates resource already exists."""
        error_code = error.response.get("Error", {}).get("Code", "")
        return ALREADY_EXISTS_ERROR in error_code or CONFLICT_ERROR in error_code

    def _update_existing_runtime(self, sanitized_name: str, config: AgentRuntimeConfig) -> str:
        """Update existing runtime and return its ARN."""
        logger.info(f"Agent runtime exists, updating: {sanitized_name}")
        existing_runtime = self._find_existing_runtime(agent_name=sanitized_name)
        self.update_agent_runtime(agent_id=existing_runtime.agentRuntimeId, config=config)
        return existing_runtime.agentRuntimeArn

    def _find_existing_runtime(self, agent_name: str) -> AgentRuntimeSummary:
        """Find existing runtime by name with pagination support."""
        next_token = None
        while True:
            response = self._list_agent_runtimes_page(next_token=next_token)
            runtime_match = self._search_runtime_in_page(response=response, agent_name=agent_name)

            if runtime_match:
                return runtime_match

            next_token = response.nextToken
            if not next_token:
                break

        raise DeploymentError(f"Could not find existing runtime: {agent_name}")

    def _list_agent_runtimes_page(self, next_token: str | None) -> ListAgentRuntimesResponse:
        """List agent runtimes for a single page."""
        request = ListAgentRuntimesRequest(nextToken=next_token)
        response = self.control_client.list_agent_runtimes(**request.model_dump(exclude_none=True))
        return ListAgentRuntimesResponse(**response)

    def _search_runtime_in_page(
        self, response: ListAgentRuntimesResponse, agent_name: str
    ) -> AgentRuntimeSummary | None:
        """Search for runtime in a single page response."""
        for runtime in response.agentRuntimes:
            if runtime.agentRuntimeName == agent_name:
                return runtime
        return None

    def _validate_json_payload(self, payload: str) -> None:
        """Validate JSON payload format."""
        try:
            json.loads(payload)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON payload: {e}")

    def _extract_agent_id_from_arn(self, agent_arn: str) -> str:
        """Extract agent ID from AgentCore ARN."""
        return agent_arn.split("/")[-1]

    def get_runtime_log_group(self, agent_arn: str) -> str:
        """Get CloudWatch runtime log group path for an agent."""
        agent_id = self._extract_agent_id_from_arn(agent_arn)
        return f"{LOG_GROUP_PREFIX}{agent_id}-{DEFAULT_ENDPOINT_NAME}"

    def get_otel_log_group(self, agent_arn: str) -> str:
        """Get CloudWatch OTEL log group path for an agent."""
        agent_id = self._extract_agent_id_from_arn(agent_arn)
        return f"{LOG_GROUP_PREFIX}{agent_id}-{DEFAULT_ENDPOINT_NAME}{OTEL_LOG_SUFFIX}"

    def get_agent_log_groups(self, agent_arn: str) -> Tuple[str, str]:
        """Get CloudWatch log group paths for an agent."""
        return self.get_runtime_log_group(agent_arn), self.get_otel_log_group(agent_arn)
