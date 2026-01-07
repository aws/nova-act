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
import os

import requests

from nova_act.impl.backends.base import ApiKeyEndpoints
from nova_act.impl.backends.burst.client import BurstClient
from nova_act.impl.backends.burst.types import (
    CreateActRequest,
    CreateActResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    CreateWorkflowRunRequest,
    CreateWorkflowRunResponse,
    InvokeActStepRequest,
    InvokeActStepResponse,
    UpdateActRequest,
    UpdateActResponse,
    UpdateWorkflowRunRequest,
    UpdateWorkflowRunResponse,
)
from nova_act.impl.backends.common import assert_json_response, get_client_source
from nova_act.types.act_errors import (
    ActAPIError,
    ActBadRequestError,
    ActClientError,
    ActDailyQuotaExceededError,
    ActGuardrailsError,
    ActInternalServerError,
    ActInvalidModelGenerationError,
    ActRateLimitExceededError,
    ActRequestThrottledError,
    ActServerError,
)


class SunburstClient(BurstClient):
    def __init__(self, endpoints: ApiKeyEndpoints, api_key: str) -> None:
        self._endpoints = endpoints

        self._api_key = api_key
        self._client_source = get_client_source().value

    def create_act(self, request: CreateActRequest) -> CreateActResponse:
        url: str = (
            f"{self._endpoints.api_url}/agent/workflow-definitions/{request.workflow_definition_name}"
            f"/workflow-runs/{request.workflow_run_id}/sessions/{request.session_id}/acts"
        )
        payload = request.model_dump(
            by_alias=True, exclude={"session_id", "workflow_definition_name", "workflow_run_id"}, exclude_none=True
        )

        response = requests.put(url=url, headers=self._headers, json=payload)
        if response.status_code != requests.codes.created:
            raise type(self)._translate_response_error(response)

        data = response.json()
        return CreateActResponse.model_validate(data)

    def create_session(self, request: CreateSessionRequest) -> CreateSessionResponse:
        url = (
            f"{self._endpoints.api_url}/agent/workflow-definitions/{request.workflow_definition_name}"
            f"/workflow-runs/{request.workflow_run_id}/sessions"
        )
        payload = request.model_dump(
            by_alias=True, exclude={"workflow_definition_name", "workflow_run_id"}, exclude_none=True
        )

        response = requests.put(url=url, headers=self._headers, json=payload)
        if response.status_code != requests.codes.created:
            raise type(self)._translate_response_error(response)

        data = response.json()
        return CreateSessionResponse.model_validate(data)

    def create_workflow_run(self, request: CreateWorkflowRunRequest) -> CreateWorkflowRunResponse:
        url = f"{self._endpoints.api_url}/agent/workflow-definitions/{request.workflow_definition_name}/workflow-runs"
        payload = request.model_dump(by_alias=True, exclude={"workflow_definition_name"}, exclude_none=True)

        response = requests.put(url=url, headers=self._headers, json=payload)
        if response.status_code != requests.codes.created:
            raise type(self)._translate_response_error(response)

        data = response.json()
        create_workflow_run_response = CreateWorkflowRunResponse.model_validate(data)
        return create_workflow_run_response

    def invoke_act_step(self, request: InvokeActStepRequest) -> InvokeActStepResponse:
        url = (
            f"{self._endpoints.api_url}/agent/workflow-definitions/{request.workflow_definition_name}"
            f"/workflow-runs/{request.workflow_run_id}/sessions/{request.session_id}/acts/{request.act_id}/invoke-step"
        )
        payload = request.model_dump(
            by_alias=True,
            exclude={"act_id", "session_id", "workflow_definition_name", "workflow_run_id"},
            exclude_none=True,
        )

        response = requests.put(url=url, headers=self._headers, json=payload)
        if response.status_code != requests.codes.ok:
            raise type(self)._translate_response_error(response)

        data = response.json()
        return InvokeActStepResponse.model_validate(data)

    def update_act(self, request: UpdateActRequest) -> UpdateActResponse:
        url = (
            f"{self._endpoints.api_url}/agent/workflow-definitions/{request.workflow_definition_name}"
            f"/workflow-runs/{request.workflow_run_id}/sessions/{request.session_id}/acts/{request.act_id}"
        )
        payload = request.model_dump(
            by_alias=True,
            exclude={"act_id", "session_id", "workflow_definition_name", "workflow_run_id"},
            exclude_none=True,
        )

        response = requests.put(url=url, headers=self._headers, json=payload)
        if response.status_code != requests.codes.ok:
            raise type(self)._translate_response_error(response)

        data = response.json()
        return UpdateActResponse.model_validate(data)

    def update_workflow_run(self, request: UpdateWorkflowRunRequest) -> UpdateWorkflowRunResponse:
        url = (
            f"{self._endpoints.api_url}/agent/workflow-definitions/{request.workflow_definition_name}"
            f"/workflow-runs/{request.workflow_run_id}"
        )
        payload = request.model_dump(
            by_alias=True, exclude={"workflow_definition_name", "workflow_run_id"}, exclude_none=True
        )

        response = requests.put(url=url, headers=self._headers, json=payload)
        if response.status_code != requests.codes.ok:
            raise type(self)._translate_response_error(response)

        data = response.json()
        return UpdateWorkflowRunResponse.model_validate(data)

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Accept-Encoding": "gzip, deflate",
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-Api-Key": self._api_key,
            "X-Client-Source": self._client_source,
        }

    @staticmethod
    def _translate_response_error(response: requests.Response) -> Exception:
        request_id = response.headers.get("x-amzn-RequestId", "")
        status_code = response.status_code

        try:
            data = assert_json_response(response, request_id)
        except Exception as e:
            return e

        if status_code == requests.codes.bad_request:
            message = f"Validation failed: {data.get('message', '')}"
            reason = data.get("reason")
            if reason == "AGENT_GUARDRAILS_TRIGGERED":
                return ActGuardrailsError(
                    message=message + f" Reason: {reason}",
                    raw_response=response.text,
                    request_id=request_id,
                    status_code=status_code,
                )
            elif reason == "INVALID_INPUT":
                fields = data.get("fields")
                fields_str = ""
                if isinstance(fields, list):
                    fields_str = " Fields: " + ", ".join(
                        [f"{f.get('name', '')}: {f.get('message', '')}" for f in fields if isinstance(f, dict)]
                    )
                return ActBadRequestError(
                    message=message + f" Reason: {reason}" + fields_str,
                    raw_response=response.text,
                    request_id=request_id,
                    status_code=status_code,
                )

            return ActBadRequestError(
                message=message,
                raw_response=response.text,
                request_id=request_id,
                status_code=status_code,
            )

        elif status_code == requests.codes.not_found:
            message = (
                f"Resource not found: {data.get('message', '')}"
                f" Resource ID: {data.get('resourceId', '')}"
                f" Resource Type: {data.get('resourceType', '')}"
            )
            return ActBadRequestError(
                message=message,
                raw_response=response.text,
                request_id=request_id,
                status_code=status_code,
            )

        elif status_code == requests.codes.too_many_requests:
            message = f"Request throttled: {data.get('message', '')}"
            throttle_type = data.get("throttleType")
            if throttle_type == "DAILY_QUOTA_LIMIT_EXCEEDED":
                return ActDailyQuotaExceededError(
                    message=message + f" Throttle Type: {throttle_type}",
                    raw_response=response.text,
                    request_id=request_id,
                    status_code=status_code,
                )
            elif throttle_type == "RATE_LIMIT_EXCEEDED":
                return ActRateLimitExceededError(
                    message=message + f" Throttle Type: {throttle_type}",
                    raw_response=response.text,
                    request_id=request_id,
                    status_code=status_code,
                )

            return ActRequestThrottledError(
                message=message,
                raw_response=response.text,
                request_id=request_id,
                status_code=status_code,
            )

        elif status_code == requests.codes.internal_server_error:
            reason = data.get("reason")
            message = f"Internal server error: {data.get('message', '')}" + (f" Reason: {reason}" if reason else "")
            if reason == "InvalidModelGeneration":
                return ActInvalidModelGenerationError(
                    message=message,
                    raw_response=response.text,
                )

            return ActInternalServerError(
                message=message,
                raw_response=response.text,
                request_id=request_id,
                status_code=status_code,
            )

        message = f"Unknown error: {data.get('message', '')}"
        # If we have an HTTP status code, group unknown errors as Server/Client
        if isinstance(status_code, int):
            if 500 <= status_code < 600:
                return ActServerError(
                    request_id=request_id,
                    status_code=status_code,
                    message=message,
                    raw_response=response.text,
                )
            elif 400 <= status_code < 500:
                return ActClientError(
                    request_id=request_id,
                    status_code=status_code,
                    message=message,
                    raw_response=response.text,
                )
        # Otherwise, default to generic ActAPIError for unknown error types
        return ActAPIError(
            message=message,
            raw_response=response.text,
            request_id=request_id,
            status_code=status_code,
        )
