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
"""Constants for AgentCore client operations."""

# Service names
BEDROCK_AGENT_CONTROL_SERVICE = "bedrock-agentcore-control"
BEDROCK_AGENT_DATA_SERVICE = "bedrock-agentcore"
STS_SERVICE = "sts"

# Timeout configuration
DEFAULT_READ_TIMEOUT = 7200  # 2 hours in seconds

# Error codes
ALREADY_EXISTS_ERROR = "AlreadyExists"
CONFLICT_ERROR = "Conflict"
RUNTIME_NOT_FOUND_ERROR = "Runtime not found"

# Log group configuration
LOG_GROUP_PREFIX = "/aws/bedrock-agentcore/runtimes/"
OTEL_LOG_SUFFIX = "/runtime-logs"

# Network configuration
PUBLIC_NETWORK_MODE = "PUBLIC"
DEFAULT_ENDPOINT_NAME = "DEFAULT"

# Agent naming
AGENT_NAME_PREFIX = "agent_"
MAX_AGENT_NAME_LENGTH = 48
