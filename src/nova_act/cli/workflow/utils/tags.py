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
"""Tag generation utilities for workflow deployments."""

from typing import Dict

# WORKFLOW_TAG_KEY helps associate AWS resources with WorkflowDefinition
WORKFLOW_TAG_KEY = "nova-act-workflow-definition-v1"


def generate_workflow_tags(workflow_definition_name: str) -> Dict[str, str]:
    """Generate standardized tags for AgentCore runtime deployment.

    Args:
        workflow_definition_name: Name of the workflow definition

    Returns:
        Dictionary of tags to apply to the AgentCore runtime
    """
    return {WORKFLOW_TAG_KEY: workflow_definition_name}
