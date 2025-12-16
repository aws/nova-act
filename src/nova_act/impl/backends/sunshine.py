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
Sunshine Backend Implementation for Nova Act SDK.

This module contains backend implementations for Sunshine environments:
- SunshineBackend: Handles API key authentication for Sunshine environments
- CloudAuthBackend: Handles internal authentication, extends SunshineBackend
"""

import json
import time
from datetime import datetime, timezone

import requests
from requests import Response
from typing_extensions import NotRequired, TypedDict

from nova_act.impl.backends.base import ApiKeyEndpoints, AwlBackend, Endpoints
from nova_act.impl.backends.common import (
    DEFAULT_REQUEST_CONNECT_TIMEOUT,
    DEFAULT_REQUEST_READ_TIMEOUT,
    assert_json_response,
    construct_step_plan_request,
)
from nova_act.impl.program.base import CallResult
from nova_act.tools.browser.interface.browser import BrowserObservation
from nova_act.types.act_errors import (
    ActBadRequestError,
    ActBadResponseError,
    ActDailyQuotaExceededError,
    ActExceededMaxStepsError,
    ActGuardrailsError,
    ActInternalServerError,
    ActInvalidModelGenerationError,
    ActRateLimitExceededError,
    ActRequestThrottledError,
    ActServiceUnavailableError,
)
from nova_act.types.api.step import StepPlanRequest
from nova_act.types.errors import AuthError
from nova_act.types.state.act import Act
from nova_act.types.state.step import ModelInput, ModelOutput, Step
from nova_act.util.logging import create_warning_box


class StepRequest(TypedDict):
    """Request to the /step endpoint."""

    actId: str
    sessionId: str
    actuationPlanRequest: str


class SunshineBackend(AwlBackend[ApiKeyEndpoints]):
    """Backend for Sunshine environments with API key authentication."""

    def get_auth_warning_message_for_backend(self, message: str) -> str:
        return create_warning_box([message, "", f"Please ensure you are using a key from: {self.endpoints.keygen_url}"])

    @classmethod
    def resolve_endpoints(
        cls,
        backend_stage: str | None = None,
        backend_api_url_override: str | None = None,
        local_port: int | None = None,
    ) -> ApiKeyEndpoints:
        api_url = "https://api.nova.amazon.com/agent"
        keygen_url = "https://nova.amazon.com/dev-apis"
        valid_api_key_length = 36


        return ApiKeyEndpoints(api_url=api_url, keygen_url=keygen_url, valid_api_key_length=valid_api_key_length)

    def __init__(
        self,
        api_key: str,
    ):
        self.api_key = api_key
        super().__init__(
        )

        self.step_uri = self.endpoints.api_url + "/step"

    def validate_auth(self) -> None:
        if len(self.api_key) != self.endpoints.valid_api_key_length:
            raise AuthError(self.get_auth_warning_message("Invalid API key length"))

    def awl_step(
        self,
        act: Act,
        observation: BrowserObservation,
        error_executing_previous_step: Exception | None = None,
        call_results: list[CallResult] | None = None,
    ) -> Step:
        """Make a step request to Sunshine backend."""
        response = self._make_step_request(self._prepare_step_request(act, observation, error_executing_previous_step))

        request_id = response.headers.get("x-amz-rid")
        status_code = response.status_code

        json_response = assert_json_response(response, request_id)

        if status_code == 200:
            if not isinstance(json_response, dict) or "actuationPlanResponse" not in json_response:
                raise ActBadResponseError(
                    request_id=request_id,
                    status_code=200,
                    message=f"Response from {self.step_uri} missing actuationPlanResponse.",
                    raw_response=response.text,
                )

            try:
                model_output = ModelOutput.from_plan_response(
                    json_response["actuationPlanResponse"],
                    request_id or "",
                )
            except LookupError:
                raise ActInvalidModelGenerationError(
                    metadata=act.metadata,
                    raw_response=response.text,
                )
            except Exception as e:
                raise ActBadResponseError(
                    request_id=request_id,
                    status_code=status_code,
                    message=f"Bad response from {self.step_uri}: {e}",
                    raw_response=response.text,
                )

            return Step(
                model_input=ModelInput(
                    image=observation["screenshotBase64"],
                    prompt=act.prompt,
                    active_url=observation["activeURL"],
                    simplified_dom=observation["simplifiedDOM"],
                ),
                model_output=model_output,
                observed_time=datetime.fromtimestamp(time.time(), tz=timezone.utc),
                server_time_s=response.elapsed.total_seconds(),
            )
        elif status_code == 400:
            reason = json_response.get("reason")
            if reason in ["MODEL_ERROR"]:
                raise ActInvalidModelGenerationError(
                    message=json_response.get("message"),
                    metadata=act.metadata,
                    raw_response=response.text,
                )
            elif reason in ["SESSION_ALREADY_STARTED", "SESSION_DOES_NOT_EXIST"]:
                raise ActBadRequestError(
                    request_id=json_response.get("RequestId", request_id),
                    status_code=status_code,
                    message=json_response.get("message"),
                    raw_response=response.text,
                )
            else:
                if reason in [
                    "INVALID_ACT_ID",
                    "INVALID_STEP_ID",
                    "INVALID_PROMPT",
                    "INVALID_SESSION_ID",
                    "INVALID_INPUT",
                    "INVALID_ACTUATION_PLAN_REQUEST",
                    "ACT_ID_ALREADY_ASSOCIATED_WITH_DIFFERENT_SESSION_ID",
                ]:
                    raise ActBadRequestError(
                        request_id=request_id,
                        status_code=status_code,
                        message=json_response.get("message"),
                        raw_response=response.text,  # this will contain `fields`
                    )
                elif reason in ["AGENT_GUARDRAILS_TRIGGERED"]:
                    raise ActGuardrailsError(
                        request_id=request_id,
                        status_code=status_code,
                        message=json_response.get("message"),
                        raw_response=response.text,  # this will contain `fields`
                    )
                elif reason in ["SESSION_SIZE_REACHED_MAX_ALLOWED_THRESHOLD"]:
                    raise ActExceededMaxStepsError(message=f"Exceeded max steps {act.max_steps} without return.")
                elif reason in ["INVALID_API_KEY_PROVIDED", "INVALID_AWS_CREDENTIALS"]:
                    raise AuthError(self.get_auth_warning_message(request_id=request_id or ""))
                else:
                    # Unknown reason
                    raise ActBadRequestError(
                        request_id=request_id,
                        status_code=status_code,
                        message=json_response.get("message"),
                        raw_response=response.text,  # this will contain `fields`
                    )
        elif status_code == 403:
            raise AuthError(self.get_auth_warning_message(request_id=request_id or ""))
        elif status_code == 404:
            raise ActBadRequestError(
                request_id=json_response.get("RequestId", request_id),
                status_code=status_code,
                message=json_response.get("message"),
                raw_response=response.text,  # this will contain `resourceId` and `resourceType`
            )
        elif status_code == 429:
            throttle_type = json_response.get("throttleType")
            if throttle_type == "DAILY_QUOTA_LIMIT_EXCEEDED":
                raise ActDailyQuotaExceededError(
                    request_id=json_response.get("RequestId", request_id),
                    status_code=status_code,
                    raw_response=response.text,  # this will contain `message`
                )
            elif throttle_type == "RATE_LIMIT_EXCEEDED":
                raise ActRequestThrottledError(
                    request_id=json_response.get("RequestId", request_id),
                    status_code=status_code,
                    raw_response=response.text,  # this will contain `message`
                )
            raise ActRateLimitExceededError(
                request_id=json_response.get("RequestId", request_id),
                status_code=status_code,
                raw_response=response.text,  # this will contain `message` and `throttleType`
            )
        elif status_code == 500:
            raise ActInternalServerError(
                request_id=json_response.get("RequestId", request_id),
                status_code=status_code,
                message=json_response.get("message"),
                raw_response=response.text,  # this will contain `reason`
            )
        elif status_code == 503:
            raise ActServiceUnavailableError(
                request_id=request_id,
                status_code=status_code,
                message=f"{self.step_uri} is unavailable.",
                raw_response=response.text,
            )
        else:
            raise ActBadResponseError(
                request_id=request_id,
                status_code=status_code,
                message=f"Received unexpected response code: {status_code}",
                raw_response=response.text,
            )

    def _prepare_step_request(
        self, act: Act, observation: BrowserObservation, error_executing_previous_step: Exception | None = None
    ) -> StepRequest:

        plan_request: StepPlanRequest = construct_step_plan_request(act, observation, error_executing_previous_step)

        payload = StepRequest(
            actId=act.id,
            sessionId=act.session_id,
            actuationPlanRequest=json.dumps(plan_request),
        )

        return payload

    def _make_step_request(self, request: StepRequest) -> Response:
        return requests.post(
            self.step_uri,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-Api-Key": f"{self.api_key}",
                "Accept-Encoding": "gzip, deflate",  # exclude zstd, which is buggy in some library versions
            },
            json=request,
            timeout=(DEFAULT_REQUEST_CONNECT_TIMEOUT, DEFAULT_REQUEST_READ_TIMEOUT),
        )
