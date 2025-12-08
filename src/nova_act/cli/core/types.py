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
"""Core type definitions for Nova Act CLI."""

from datetime import datetime
from typing import Dict

from pydantic import BaseModel, Field

from nova_act.cli.core.constants import BUILD_TEMP_DIR, DEFAULT_ENTRY_POINT


class ServiceDeployment(BaseModel):
    """Represents a service deployment with ARN."""

    deployment_arn: str
    image_uri: str


class AgentCoreDeployment(BaseModel):
    """Represents an AgentCore deployment result."""

    deployment_arn: str
    image_uri: str
    image_tag: str


class WorkflowDeployments(BaseModel):
    """Service-based deployment structure."""

    agentcore: AgentCoreDeployment | None = None


class WorkflowInfo(BaseModel):
    """Workflow information with per-region WorkflowDefinition ARN."""

    name: str
    directory_path: str
    created_at: datetime
    workflow_definition_arn: str | None = None
    deployments: WorkflowDeployments = Field(default_factory=WorkflowDeployments)
    metadata: Dict[str, str] | None = None
    last_image_tag: str | None = None


class BuildConfig(BaseModel):
    """Build configuration settings."""

    default_entry_point: str = DEFAULT_ENTRY_POINT
    temp_dir: str = BUILD_TEMP_DIR


class ThemeConfig(BaseModel):
    """Theme configuration settings."""

    name: str = "default"
    enabled: bool = True


class UserConfig(BaseModel):
    """User configuration preferences (YAML-based)."""

    build: BuildConfig = Field(default_factory=BuildConfig)
    theme: ThemeConfig = Field(default_factory=ThemeConfig)


class RegionState(BaseModel):
    """Per-region workflow state."""

    workflows: Dict[str, WorkflowInfo] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=datetime.now)
    version: str = "1.0"


class StateLockInfo(BaseModel):
    """State file locking information."""

    lock_file: str  # Using str instead of Path for JSON serialization
    timeout: int = 30


class RegionContext(BaseModel):
    """Region and account context for deployment operations."""

    region: str
    account_id: str
