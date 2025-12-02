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
Minimal client for WorkflowDefinition operations.
"""

import logging
from importlib.resources import files

from boto3 import Session

from nova_act.cli.core.clients.nova_act.constants import DEFAULT_SERVICE_NAME
from nova_act.cli.core.clients.nova_act.types import (
    CreateWorkflowDefinitionRequest,
    CreateWorkflowDefinitionResponse,
    DeleteWorkflowDefinitionRequest,
    DeleteWorkflowDefinitionResponse,
    GetWorkflowDefinitionRequest,
    GetWorkflowDefinitionResponse,
)
from nova_act.cli.core.constants import DEFAULT_REGION

logger = logging.getLogger(__name__)


class NovaActClient:
    """Minimal client for WorkflowDefinition operations."""

    def __init__(
        self,
        boto_session: Session,
        region_name: str = DEFAULT_REGION,
    ):
        client_kwargs = {"service_name": DEFAULT_SERVICE_NAME, "region_name": region_name}
        self._client = boto_session.client(**client_kwargs)  # type: ignore[call-overload]

    def create_workflow_definition(self, request: CreateWorkflowDefinitionRequest) -> CreateWorkflowDefinitionResponse:
        """Create a workflow definition."""
        params = request.model_dump(exclude_none=True)
        response = self._client.create_workflow_definition(**params)
        result = CreateWorkflowDefinitionResponse.model_validate(response)
        logger.info(f"Successfully created workflow definition: {request.name}")
        return result

    def get_workflow_definition(self, request: GetWorkflowDefinitionRequest) -> GetWorkflowDefinitionResponse:
        """Get a workflow definition."""
        params = request.model_dump(exclude_none=True)
        response = self._client.get_workflow_definition(**params)
        return GetWorkflowDefinitionResponse.model_validate(response)

    def delete_workflow_definition(self, request: DeleteWorkflowDefinitionRequest) -> DeleteWorkflowDefinitionResponse:
        """Delete a workflow definition."""
        params = request.model_dump(exclude_none=True)
        response = self._client.delete_workflow_definition(**params)
        return DeleteWorkflowDefinitionResponse.model_validate(response)
