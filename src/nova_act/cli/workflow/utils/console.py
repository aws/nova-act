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
"""AWS Console URL utilities for Nova Act CLI."""


def build_bedrock_agentcore_console_url(region: str, agent_id: str) -> str:
    """Build console URL for Bedrock AgentCore agent.

    Args:
        region: AWS region (e.g., 'us-east-1')
        agent_id: Agent ID extracted from ARN

    Returns:
        Console URL for the agent
    """
    return f"https://{region}.console.aws.amazon.com/bedrock-agentcore/agents/{agent_id}"


def build_nova_act_workflow_console_url(region: str, workflow_definition_name: str) -> str:
    """Build console URL for Nova Act workflow definition.

    Args:
        region: AWS region (e.g., 'us-east-1')
        workflow_definition_name: Workflow definition name

    Returns:
        Console URL for the workflow definition
    """
    return f"https://{region}.console.aws.amazon.com/nova-act/home#/workflow-definitions/{workflow_definition_name}"
