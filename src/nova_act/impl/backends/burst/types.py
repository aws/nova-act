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
from __future__ import annotations

import json
from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, Field
from strands.types.tools import ToolSpec

from nova_act.__version__ import VERSION
from nova_act.impl.program.base import Call as SdkCall
from nova_act.impl.program.base import CallResult as SdkCallResult
from nova_act.types.api.status import ActStatus, WorkflowRunStatus
from nova_act.types.json_type import JSONType
from nova_act.util.argument_preparation import prepare_kwargs_for_actuation_calls
from nova_act.util.logging import setup_logging

_LOGGER = setup_logging(__name__)


class Pattern:
    NON_BLANK_STRING = "^[\\s\\S]+$"
    UUID = "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"


class ActErrorData(BaseModel):
    """Content of ErrorData for UpdateAct.

    """

    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)

    message: str = Field(
        ...,
        max_length=10000,
        min_length=1,
        description="Error message describing what went wrong",
    )
    type: str | None = Field(
        None,
        max_length=100,
        min_length=1,
        description="Optional error type classification",
    )


class Call(BaseModel):
    """A tool call to be executed.

    """

    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)

    call_id: str = Field(alias="callId", max_length=100, min_length=1)
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


Calls: TypeAlias = list[Call]


class CallResultContent(BaseModel):
    """Content of a call result - either JSON or text (union type).

    """

    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)

    text: str


CallResultContents: TypeAlias = list[CallResultContent]


class CallResult(BaseModel):
    """Result of a tool call execution.

    """

    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)

    call_id: str | None = Field(None, alias="callId", max_length=100, min_length=1)
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


CallResults: TypeAlias = list[CallResult]


class ClientInfo(BaseModel):
    """SDK client compatibility info.

    """

    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)

    compatibility_version: int = Field(alias="compatibilityVersion")
    sdk_version: str = Field(pattern=Pattern.NON_BLANK_STRING, alias="sdkVersion")


class CommonField:
    ACT_ID: str = Field(alias="actId", pattern=Pattern.UUID)
    CLIENT_TOKEN: str | None = Field(
        None,
        alias="clientToken",
        max_length=256,
        min_length=33,
        pattern="^[a-zA-Z0-9](-*[a-zA-Z0-9]){0,256}$",
    )
    SESSION_ID = Field(alias="sessionId", pattern=Pattern.UUID)
    WORKFLOW_DEFINITION_NAME: str = Field(
        alias="workflowDefinitionName",
        max_length=40,
        min_length=1,
        pattern="^[a-zA-Z0-9_-]{1,40}$",
    )
    WORKFLOW_RUN_ID: str = Field(alias="workflowRunId", pattern="^[a-zA-Z0-9-_]{1,40}$")


class CreateActRequest(BaseModel):
    """Request for creating an act.

    """

    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)

    client_token: str | None = CommonField.CLIENT_TOKEN
    session_id: str = CommonField.SESSION_ID
    task: str
    tool_specs: list[ToolSpec] | None = Field(None, alias="toolSpecs")
    workflow_definition_name: str = CommonField.WORKFLOW_DEFINITION_NAME
    workflow_run_id: str = CommonField.WORKFLOW_RUN_ID


class CreateActResponse(BaseModel):
    """Response from creating an act.

    """

    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)

    act_id: str = CommonField.ACT_ID
    status: ActStatus


class CreateSessionRequest(BaseModel):
    """Request for creating a session.

    """

    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)

    client_token: str | None = CommonField.CLIENT_TOKEN
    workflow_definition_name: str = CommonField.WORKFLOW_DEFINITION_NAME
    workflow_run_id: str = CommonField.WORKFLOW_RUN_ID


class CreateSessionResponse(BaseModel):
    """Response from creating a session.

    """

    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)

    session_id: str = CommonField.SESSION_ID


class CreateWorkflowRunRequest(BaseModel):
    """Request for creating a workflow run.

    """

    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)

    client_info: ClientInfo = Field(
        alias="clientInfo",
        default_factory=lambda: ClientInfo(compatibility_version=1, sdk_version=VERSION),
    )
    client_token: str | None = CommonField.CLIENT_TOKEN
    log_group_name: str | None = Field(
        None,
        alias="logGroupName",
        max_length=512,
        min_length=1,
        pattern="^[a-zA-Z0-9_/.-]+$",
    )
    model_id: str = Field(alias="modelId", max_length=100, min_length=1)
    workflow_definition_name: str = CommonField.WORKFLOW_DEFINITION_NAME


class CreateWorkflowRunResponse(BaseModel):
    """Response from creating a workflow run.

    """

    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)

    status: WorkflowRunStatus
    workflow_run_id: str = CommonField.WORKFLOW_RUN_ID


class InvokeActStepRequest(BaseModel):
    """Request for invoking an act step.

    """

    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)

    act_id: str = CommonField.ACT_ID
    call_results: list[CallResult] = Field(alias="callResults")
    previous_step_id: str | None = Field(None, alias="previousStepId", pattern=Pattern.UUID)
    session_id: str = CommonField.SESSION_ID
    workflow_definition_name: str = CommonField.WORKFLOW_DEFINITION_NAME
    workflow_run_id: str = CommonField.WORKFLOW_RUN_ID


class InvokeActStepResponse(BaseModel):
    """Response from invoking an act step.

    """

    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)

    calls: Calls
    step_id: str = Field(alias="stepId", pattern=Pattern.UUID)


class UpdateActRequest(BaseModel):
    """Request for updating an act.

    """

    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)

    act_id: str = CommonField.ACT_ID
    error: ActErrorData | None = None
    session_id: str = CommonField.SESSION_ID
    status: ActStatus
    workflow_definition_name: str = CommonField.WORKFLOW_DEFINITION_NAME
    workflow_run_id: str = CommonField.WORKFLOW_RUN_ID


class UpdateActResponse(BaseModel):
    """Response from updating an act.

    """

    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)


class UpdateWorkflowRunRequest(BaseModel):
    """Request for updating a workflow run.

    """

    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)

    status: WorkflowRunStatus
    workflow_definition_name: str = CommonField.WORKFLOW_DEFINITION_NAME
    workflow_run_id: str = CommonField.WORKFLOW_RUN_ID


class UpdateWorkflowRunResponse(BaseModel):
    """Response from updating a workflow run.

    """

    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)
