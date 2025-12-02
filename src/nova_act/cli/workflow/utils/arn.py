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
"""ARN utilities for workflow definitions."""

import re


def construct_workflow_definition_arn(name: str, region: str, account_id: str) -> str:
    """Construct a workflow definition ARN."""
    return f"arn:aws:nova-act:{region}:{account_id}:workflow-definition/{name}"


def extract_agent_id_from_arn(agent_arn: str) -> str:
    """Extract agent ID from agent ARN.

    Args:
        agent_arn: Full agent ARN (e.g., 'arn:aws:bedrock:us-east-1:123456789012:agent/agent-id')

    Returns:
        Agent ID extracted from ARN

    Example:
        >>> extract_agent_id_from_arn('arn:aws:bedrock:us-east-1:123456789012:agent/ABCD1234')
        'ABCD1234'
    """
    return agent_arn.split("/")[-1]


def extract_workflow_definition_name_from_arn(workflow_definition_arn: str) -> str:
    """Extract workflow definition name from ARN.

    Args:
        workflow_definition_arn: Full workflow definition ARN

    Returns:
        Workflow definition name extracted from ARN
    """
    return workflow_definition_arn.split("/")[-1]


def validate_workflow_definition_arn(arn: str) -> None:
    """Validate nova-act workflow definition ARN format."""
    # Handle None input
    if arn is None:
        raise ValueError("ARN cannot be None")

    # Handle empty string
    if not arn or not arn.strip():
        raise ValueError("ARN cannot be empty")

    # Regex validation
    pattern = r"^arn:aws:nova-act:[^:]+:\d{12}:workflow-definition/.+$"
    if not re.match(pattern=pattern, string=arn):
        raise ValueError(f"Invalid nova-act workflow definition ARN format: {arn}")
