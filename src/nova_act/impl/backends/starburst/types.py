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
Enhanced Pydantic types for Nova Act service communication based on Smithy model.
Each type includes `to` and `from` methods for seamless conversion between SDK and service types.
"""

from __future__ import annotations

import json
from typing import TypeAlias

from pydantic import BaseModel, Field
from strands.types.tools import ToolSpec

from nova_act.__version__ import VERSION
from nova_act.impl.program.base import Call as SdkCall
from nova_act.impl.program.base import CallResult as SdkCallResult
from nova_act.types.api.status import ActStatus, WorkflowRunStatus
from nova_act.types.json_type import JSONType
from nova_act.util.argument_preparation import prepare_kwargs_for_actuation_calls
from nova_act.util.logging import (
    setup_logging,
)

_LOGGER = setup_logging(__name__)

# Constants
S_TO_MS = 1000  # Seconds to milliseconds conversion factor
CALL_ID_MAX_LENGTH = 100
CALL_ID_MIN_LENGTH = 1
CLIENT_TOKEN_MAX_LENGTH = 256
CLIENT_TOKEN_MIN_LENGTH = 33
CLIENT_TOKEN_PATTERN = "^[a-zA-Z0-9](-*[a-zA-Z0-9]){0,256}$"
CLOUD_WATCH_LOG_GROUP_MAX_LENGTH = 512
CLOUD_WATCH_LOG_GROUP_MIN_LENGTH = 1
CLOUD_WATCH_LOG_GROUP_PATTERN = "^[a-zA-Z0-9_/.-]+$"
MODEL_ID_MAX_LENGTH = 100
MODEL_ID_MIN_LENGTH = 1
NON_BLANK_STRING_PATTERN = "^[\\s\\S]+$"
UUID_PATTERN = "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
WORKFLOW_DEFINITION_MAX_LENGTH = 40
WORKFLOW_DEFINITION_MIN_LENGTH = 1
WORKFLOW_DEFINITION_PATTERN = "^[a-zA-Z0-9_-]{1,40}$"

# ActError field constraints
ACT_ERROR_MESSAGE_MAX_LENGTH = 10000
ACT_ERROR_MESSAGE_MIN_LENGTH = 1
ACT_ERROR_TYPE_MAX_LENGTH = 100
ACT_ERROR_TYPE_MIN_LENGTH = 1


class ActErrorData(BaseModel):
    """Content of ErrorData for UpdateAct.

    """

    message: str = Field(
        ...,
        max_length=ACT_ERROR_MESSAGE_MAX_LENGTH,
        min_length=ACT_ERROR_MESSAGE_MIN_LENGTH,
        description="Error message describing what went wrong",
    )
    type: str | None = Field(
        None,
        max_length=ACT_ERROR_TYPE_MAX_LENGTH,
        min_length=ACT_ERROR_TYPE_MIN_LENGTH,
        description="Optional error type classification",
    )

    model_config = {"populate_by_name": True}


class CallResultContent(BaseModel):
    """Content of a call result - either JSON or text (union type).

    """

    text: str

    model_config = {"populate_by_name": True}


CallResultContents: TypeAlias = list[CallResultContent]


class CallResult(BaseModel):
    """Result of a tool call execution.

    """

    call_id: str | None = Field(None, alias="callId", max_length=CALL_ID_MAX_LENGTH, min_length=CALL_ID_MIN_LENGTH)
    content: CallResultContents

    @classmethod
    def from_sdk_call_result(cls, sdk_call_result: SdkCallResult) -> CallResult:
        """Convert from SDK CallResult to service CallResult."""
        _LOGGER.debug("Converting SDK CallResult:")
        _LOGGER.debug(f"  call.name: {sdk_call_result.call.name}")
        _LOGGER.debug(f"  return_value type: {type(sdk_call_result.return_value)}")
        # Truncate screenshotBase64 for logging only
        return_value_for_log = sdk_call_result.return_value
        if isinstance(return_value_for_log, dict) and "screenshotBase64" in return_value_for_log:
            return_value_for_log = return_value_for_log.copy()
            return_value_for_log["screenshotBase64"] = "...[truncated chars]..."
        _LOGGER.debug(f"  return_value: {return_value_for_log}")
        _LOGGER.debug(f"  error: {sdk_call_result.error}")

        # Format the return value as JSON string
        formatted_return_value = json.dumps(sdk_call_result.return_value)

        result = cls(
            call_id=sdk_call_result.call.id,
            content=[CallResultContent(text=formatted_return_value)],
        )
        _LOGGER.debug(f"  created CallResult: {result}")
        return result

    model_config = {"populate_by_name": True}


CallResults: TypeAlias = list[CallResult]


class Call(BaseModel):
    """A tool call to be executed.

    """

    call_id: str = Field(alias="callId", max_length=CALL_ID_MAX_LENGTH, min_length=CALL_ID_MIN_LENGTH)
    input: list[JSONType] | dict[str, JSONType]
    name: str

    def to_sdk_call(self) -> SdkCall:
        """Convert to SDK Call."""
        from nova_act.impl.program.base import Call as SdkCall

        if isinstance(self.input, dict):
            kwargs = self.input
            is_tool = True
        else:
            # If input is a list, convert to dict with indexed keys
            kwargs = prepare_kwargs_for_actuation_calls(self.name, self.input)
            is_tool = False

        return SdkCall(name=self.name, kwargs=kwargs, id=self.call_id, is_tool=is_tool)

    model_config = {"populate_by_name": True}


Calls: TypeAlias = list[Call]


class ResponseMetadata(BaseModel):
    """AWS response metadata included in all service responses."""

    request_id: str = Field(alias="RequestId")
    http_status_code: int = Field(alias="HTTPStatusCode")
    http_headers: dict[str, str] = Field(default_factory=dict, alias="HTTPHeaders")
    retry_attempts: int = Field(default=0, alias="RetryAttempts")
    elapsed_time_ms: float | None = Field(
        None, alias="elapsed_time_ms", description="Request elapsed time in milliseconds"
    )

    def get_elapsed_time_formatted(self) -> str:
        """Get formatted elapsed time string."""
        if self.elapsed_time_ms is None:
            return "N/A"
        elif self.elapsed_time_ms < S_TO_MS:
            return f"{self.elapsed_time_ms:.1f}ms"
        else:
            return f"{self.elapsed_time_ms / S_TO_MS:.2f}s"

    model_config = {"populate_by_name": True}


class InvokeActStepRequest(BaseModel):
    """Request for invoking an act step.

    """

    workflow_definition_name: str = Field(
        alias="workflowDefinitionName",
        max_length=WORKFLOW_DEFINITION_MAX_LENGTH,
        min_length=WORKFLOW_DEFINITION_MIN_LENGTH,
        pattern=WORKFLOW_DEFINITION_PATTERN,
    )
    workflow_run_id: str = Field(alias="workflowRunId", pattern=UUID_PATTERN)
    session_id: str = Field(alias="sessionId", pattern=UUID_PATTERN)
    act_id: str = Field(alias="actId", pattern=UUID_PATTERN)
    call_results: CallResults = Field(alias="callResults")
    previous_step_id: str | None = Field(None, alias="previousStepId", pattern=UUID_PATTERN)

    @classmethod
    def from_sdk_data(
        cls,
        workflow_definition_name: str,
        workflow_run_id: str,
        session_id: str,
        act_id: str,
        sdk_call_results: list[SdkCallResult],
        previous_step_id: str | None = None,
    ) -> InvokeActStepRequest:
        """Create request from SDK data."""
        service_call_results: CallResults = [
            CallResult.from_sdk_call_result(sdk_call_result) for sdk_call_result in sdk_call_results
        ]

        return cls(
            workflow_definition_name=workflow_definition_name,
            workflow_run_id=workflow_run_id,
            session_id=session_id,
            act_id=act_id,
            call_results=service_call_results,
            previous_step_id=previous_step_id,
        )

    model_config = {"populate_by_name": True}


class InvokeActStepResponse(BaseModel):
    """Response from invoking an act step.

    """

    calls: Calls
    step_id: str = Field(alias="stepId", pattern=UUID_PATTERN)
    response_metadata: ResponseMetadata = Field(alias="ResponseMetadata")

    def get_request_id(self) -> str:
        """Get the request ID from response metadata."""
        return self.response_metadata.request_id

    def get_step_id(self) -> str:
        """Get the step ID from the response."""
        return self.step_id

    model_config = {"populate_by_name": True}


class CreateActRequest(BaseModel):
    """Request for creating an act.

    """

    workflow_definition_name: str = Field(
        alias="workflowDefinitionName",
        max_length=WORKFLOW_DEFINITION_MAX_LENGTH,
        min_length=WORKFLOW_DEFINITION_MIN_LENGTH,
        pattern=WORKFLOW_DEFINITION_PATTERN,
    )
    workflow_run_id: str = Field(alias="workflowRunId", pattern=UUID_PATTERN)
    session_id: str = Field(alias="sessionId", pattern=UUID_PATTERN)
    task: str
    tool_specs: list[ToolSpec] | None = Field(None, alias="toolSpecs")
    client_token: str | None = Field(
        None,
        alias="clientToken",
        max_length=CLIENT_TOKEN_MAX_LENGTH,
        min_length=CLIENT_TOKEN_MIN_LENGTH,
        pattern=CLIENT_TOKEN_PATTERN,
    )

    @classmethod
    def from_sdk_data(
        cls,
        workflow_definition_name: str,
        workflow_run_id: str,
        session_id: str,
        task: str,
        tool_specs: list[ToolSpec] | None = None,
        client_token: str | None = None,
    ) -> CreateActRequest:
        """Create request from SDK data."""

        return cls(
            workflow_definition_name=workflow_definition_name,
            workflow_run_id=workflow_run_id,
            session_id=session_id,
            task=task,
            tool_specs=tool_specs,
            client_token=client_token,
        )

    model_config = {"populate_by_name": True}


class CreateActResponse(BaseModel):
    """Response from creating an act.

    """

    act_id: str = Field(alias="actId", pattern=UUID_PATTERN)
    status: ActStatus
    response_metadata: ResponseMetadata = Field(alias="ResponseMetadata")

    def get_request_id(self) -> str:
        """Get the request ID from response metadata."""
        return self.response_metadata.request_id

    model_config = {"populate_by_name": True}


class CreateSessionRequest(BaseModel):
    """Request for creating a session.

    """

    workflow_definition_name: str = Field(
        alias="workflowDefinitionName",
        max_length=WORKFLOW_DEFINITION_MAX_LENGTH,
        min_length=WORKFLOW_DEFINITION_MIN_LENGTH,
        pattern=WORKFLOW_DEFINITION_PATTERN,
    )
    workflow_run_id: str = Field(alias="workflowRunId", pattern=UUID_PATTERN)
    client_token: str | None = Field(
        None,
        alias="clientToken",
        max_length=CLIENT_TOKEN_MAX_LENGTH,
        min_length=CLIENT_TOKEN_MIN_LENGTH,
        pattern=CLIENT_TOKEN_PATTERN,
    )

    @classmethod
    def from_sdk_data(
        cls, workflow_definition_name: str, workflow_run_id: str, client_token: str | None = None
    ) -> CreateSessionRequest:
        """Create request from SDK data."""
        return cls(
            workflow_definition_name=workflow_definition_name,
            workflow_run_id=workflow_run_id,
            client_token=client_token,
        )

    model_config = {"populate_by_name": True}


class CreateSessionResponse(BaseModel):
    """Response from creating a session.

    """

    session_id: str = Field(alias="sessionId", pattern=UUID_PATTERN)
    response_metadata: ResponseMetadata = Field(alias="ResponseMetadata")

    def get_request_id(self) -> str:
        """Get the request ID from response metadata."""
        return self.response_metadata.request_id

    model_config = {"populate_by_name": True}


class UpdateActRequest(BaseModel):
    """Request for updating an act.

    """

    workflow_definition_name: str = Field(
        alias="workflowDefinitionName",
        max_length=WORKFLOW_DEFINITION_MAX_LENGTH,
        min_length=WORKFLOW_DEFINITION_MIN_LENGTH,
        pattern=WORKFLOW_DEFINITION_PATTERN,
    )
    workflow_run_id: str = Field(alias="workflowRunId", pattern=UUID_PATTERN)
    session_id: str = Field(alias="sessionId", pattern=UUID_PATTERN)
    act_id: str = Field(alias="actId", pattern=UUID_PATTERN)
    status: ActStatus
    error: ActErrorData | None = None

    model_config = {"populate_by_name": True}


class UpdateActResponse(BaseModel):
    """Response from updating an act.

    """

    response_metadata: ResponseMetadata = Field(alias="ResponseMetadata")

    def get_request_id(self) -> str:
        """Get the request ID from response metadata."""
        return self.response_metadata.request_id

    model_config = {"populate_by_name": True}


class ClientInfo(BaseModel):
    """SDK client compatibility info.

    """

    compatibility_version: int = Field(alias="compatibilityVersion")
    sdk_version: str = Field(pattern=NON_BLANK_STRING_PATTERN, alias="sdkVersion")


class CreateWorkflowRunRequest(BaseModel):
    """Request for creating a workflow run.

    """

    workflow_definition_name: str = Field(
        alias="workflowDefinitionName",
        max_length=WORKFLOW_DEFINITION_MAX_LENGTH,
        min_length=WORKFLOW_DEFINITION_MIN_LENGTH,
        pattern=WORKFLOW_DEFINITION_PATTERN,
    )
    model_id: str = Field(alias="modelId", max_length=MODEL_ID_MAX_LENGTH, min_length=MODEL_ID_MIN_LENGTH)
    client_token: str | None = Field(
        None,
        alias="clientToken",
        max_length=CLIENT_TOKEN_MAX_LENGTH,
        min_length=CLIENT_TOKEN_MIN_LENGTH,
        pattern=CLIENT_TOKEN_PATTERN,
    )
    log_group_name: str | None = Field(
        None,
        alias="logGroupName",
        max_length=CLOUD_WATCH_LOG_GROUP_MAX_LENGTH,
        min_length=CLOUD_WATCH_LOG_GROUP_MIN_LENGTH,
        pattern=CLOUD_WATCH_LOG_GROUP_PATTERN,
    )
    client_info: ClientInfo = Field(
        default_factory=lambda: ClientInfo(compatibilityVersion=1, sdkVersion=VERSION), alias="clientInfo"
    )

    @classmethod
    def from_sdk_data(
        cls,
        workflow_definition_name: str,
        log_group_name: str | None,
        model_id: str,
        client_token: str | None = None,
        client_info: ClientInfo | None = None,
    ) -> CreateWorkflowRunRequest:
        """Create request from SDK data."""

        return cls(
            workflow_definition_name=workflow_definition_name,
            log_group_name=log_group_name,
            model_id=model_id,
            client_token=client_token,
            **(dict(client_info=client_info) if client_info is not None else {}),
        )

    model_config = {"populate_by_name": True}


class CreateWorkflowRunResponse(BaseModel):
    """Response from creating a workflow run.

    """

    workflow_run_id: str = Field(alias="workflowRunId", pattern=UUID_PATTERN)
    status: WorkflowRunStatus
    response_metadata: ResponseMetadata = Field(alias="ResponseMetadata")

    def get_request_id(self) -> str:
        """Get the request ID from response metadata."""
        return self.response_metadata.request_id

    model_config = {"populate_by_name": True}


class UpdateWorkflowRunRequest(BaseModel):
    """Request for updating a workflow run.

    """

    workflow_definition_name: str = Field(
        alias="workflowDefinitionName",
        max_length=WORKFLOW_DEFINITION_MAX_LENGTH,
        min_length=WORKFLOW_DEFINITION_MIN_LENGTH,
        pattern=WORKFLOW_DEFINITION_PATTERN,
    )
    workflow_run_id: str = Field(alias="workflowRunId", pattern=UUID_PATTERN)
    status: WorkflowRunStatus

    @classmethod
    def from_sdk_data(
        cls,
        workflow_definition_name: str,
        workflow_run_id: str,
        status: WorkflowRunStatus,
    ) -> UpdateWorkflowRunRequest:
        """Create request from SDK data."""
        return cls(
            workflow_definition_name=workflow_definition_name,
            workflow_run_id=workflow_run_id,
            status=status,
        )

    model_config = {"populate_by_name": True}


class UpdateWorkflowRunResponse(BaseModel):
    """Response from updating a workflow run.

    """

    response_metadata: ResponseMetadata = Field(alias="ResponseMetadata")

    def get_request_id(self) -> str:
        """Get the request ID from response metadata."""
        return self.response_metadata.request_id

    model_config = {"populate_by_name": True}
