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
"""Pydantic types for AgentCore client operations."""

from typing import Dict, List

from pydantic import BaseModel


class ContainerConfiguration(BaseModel):
    """Container configuration for agent runtime."""

    model_config = {"extra": "allow"}

    containerUri: str


class AgentRuntimeArtifact(BaseModel):
    """Agent runtime artifact configuration."""

    model_config = {"extra": "allow"}

    containerConfiguration: ContainerConfiguration


class AgentRuntimeConfig(BaseModel):
    """Configuration for AgentCore Runtime."""

    model_config = {"extra": "allow"}

    container_uri: str
    role_arn: str
    environment_variables: Dict[str, str] | None = None
    tags: Dict[str, str] | None = None


class AgentRuntimeResponse(BaseModel):
    """Response from AgentCore Runtime operations."""

    model_config = {"extra": "allow"}

    agentRuntimeArn: str


# Control Client Request Types
class CreateAgentRuntimeRequest(BaseModel):
    """Request for creating agent runtime."""

    model_config = {"extra": "allow"}

    agentRuntimeName: str
    agentRuntimeArtifact: AgentRuntimeArtifact
    roleArn: str
    networkConfiguration: Dict[str, str]
    environmentVariables: Dict[str, str] | None = None
    tags: Dict[str, str] | None = None


class UpdateAgentRuntimeRequest(BaseModel):
    """Request for updating agent runtime."""

    model_config = {"extra": "allow"}

    agentRuntimeId: str
    agentRuntimeArtifact: AgentRuntimeArtifact
    roleArn: str
    networkConfiguration: Dict[str, str]
    environmentVariables: Dict[str, str] | None = None


class ListAgentRuntimesRequest(BaseModel):
    """Request for listing agent runtimes."""

    model_config = {"extra": "allow"}

    nextToken: str | None = None


# Control Client Response Types
class CreateAgentRuntimeResponse(BaseModel):
    """Response from creating agent runtime."""

    model_config = {"extra": "allow"}

    agentRuntimeArn: str


class UpdateAgentRuntimeResponse(BaseModel):
    """Response from updating agent runtime."""

    model_config = {"extra": "allow"}

    agentRuntimeArn: str


class AgentRuntimeSummary(BaseModel):
    """Summary of agent runtime in list response."""

    model_config = {"extra": "allow"}

    agentRuntimeId: str
    agentRuntimeName: str
    agentRuntimeArn: str


class ListAgentRuntimesResponse(BaseModel):
    """Response from listing agent runtimes."""

    model_config = {"extra": "allow"}

    agentRuntimes: List[AgentRuntimeSummary]
    nextToken: str | None = None


# Data Client Request Types
class InvokeAgentRuntimeRequest(BaseModel):
    """Request for invoking agent runtime."""

    model_config = {"extra": "allow"}

    agentRuntimeArn: str
    runtimeSessionId: str
    payload: str


# Data Client Response Types
class InvokeAgentRuntimeResponse(BaseModel):
    """Response from invoking agent runtime.

    Matches the structure expected by response_parser.parse_invoke_response().
    """

    model_config = {"extra": "allow"}

    response: Dict[str, object]
    contentType: str | None = None  # MIME type for response parsing
