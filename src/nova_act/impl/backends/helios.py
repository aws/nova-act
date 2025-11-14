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
import json
import time
from datetime import datetime, timezone

import botocore.auth
import requests
from boto3.session import Session
from botocore.awsrequest import AWSRequest
from requests import Response
from typing_extensions import TypedDict, cast

from nova_act.impl.backends.base import AwlBackend, Endpoints
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
    ActGuardrailsError,
    ActInternalServerError,
    ActInvalidModelGenerationError,
    ActRequestThrottledError,
    ActTimeoutError,
)
from nova_act.types.api.step import PlanResponse, StepPlanRequest
from nova_act.types.api.trace import TraceDict
from nova_act.types.errors import (
    AuthError,
    IAMAuthError,
)
from nova_act.types.state.act import Act
from nova_act.types.state.step import ModelInput, ModelOutput, Step
from nova_act.util.logging import create_warning_box


class PlanInputDict(TypedDict):
    """Container for plan request data."""

    planRequest: StepPlanRequest


class HeliosRequestDict(TypedDict):
    """Complete request structure for Helios service."""

    enableTrace: bool
    nexusActId: str
    nexusSessionId: str
    planInput: PlanInputDict


# Base response structures
class PlanOutputDict(TypedDict):
    """Container for plan response data."""

    planResponse: PlanResponse


class HeliosResponseDict(TypedDict):
    """Complete response structure from Helios service."""

    planOutput: PlanOutputDict
    trace: TraceDict | None


class HeliosBackend(AwlBackend[Endpoints]):

    def __init__(
        self,
        boto_session: Session,
    ):
        self.boto_session = boto_session
        super().__init__(
        )
        self.step_url = f"{self.endpoints.api_url}/nova-act/invoke"

    def validate_auth(self) -> None:
        self._validate_boto_session()

    def awl_step(
        self,
        act: Act,
        observation: BrowserObservation,
        error_executing_previous_step: Exception | None = None,
        call_results: list[CallResult] | None = None,
    ) -> Step:
        """Make a step request to Helios backend."""
        response = self._make_step_request(self._prepare_step_request(act, observation, error_executing_previous_step))

        status_code = response.status_code

        json_response = assert_json_response(response)

        if status_code == 200:
            if (
                not isinstance(json_response, dict)
                or "planOutput" not in json_response
                or "planResponse" not in json_response["planOutput"]
            ):
                raise ActBadResponseError(
                    status_code=status_code,
                    message=f"Response from {self.step_url} missing planOutput..planResponse.",
                    raw_response=response.text,
                )
            cast(HeliosResponseDict, json_response)

            try:
                model_output = ModelOutput.from_plan_response(
                    json.dumps(json_response["planOutput"]["planResponse"]),
                )
            except LookupError:
                raise ActInvalidModelGenerationError(
                    metadata=act.metadata,
                    raw_response=response.text,
                )
            except Exception as e:
                raise ActBadResponseError(
                    status_code=status_code,
                    message=f"Bad response from {self.step_url}: {e}",
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
                trace=json_response.get("trace"),
            )
        else:
            if isinstance(json_response, dict) and "error" in json_response and "code" in json_response["error"]:
                error = json_response["error"]
                code: str = error["code"]
                message: str = error.get("message")
                raw_response = response.text  # this will contain `.error..code`

                if code == "INVALID_INPUT":
                    raise ActBadRequestError(
                        status_code=status_code,
                        message=message,
                        raw_response=raw_response,
                    )
                elif code == "MODEL_ERROR":
                    raise ActInvalidModelGenerationError(
                        message=message,
                        metadata=act.metadata,
                        raw_response=raw_response,
                    )
                elif code == "INTERNAL_ERROR":
                    raise ActInternalServerError(
                        status_code=status_code,
                        message=message,
                        raw_response=raw_response,
                    )
                elif code == "GUARDRAILS_ERROR":
                    raise ActGuardrailsError(
                        status_code=status_code,
                        message=message,
                        raw_response=raw_response,
                    )
                elif code == "UNAUTHORIZED_ERROR":
                    raise AuthError(self.get_auth_warning_message())
                elif code == "TOO_MANY_REQUESTS":
                    raise ActRequestThrottledError(
                        status_code=status_code,
                        raw_response=raw_response,
                    )
                elif code == "DAILY_QUOTA_LIMIT_ERROR":
                    raise ActDailyQuotaExceededError(
                        status_code=status_code,
                        raw_response=raw_response,
                    )
                elif code == "SESSION_EXPIRED_ERROR":
                    raise ActTimeoutError(f"Session expired in NovaAct backend: {raw_response}")
                else:
                    raise ActBadResponseError(
                        status_code=status_code,
                        message=f"Response from {self.step_url} contains unknown error code: {code}.",
                        raw_response=response.text,
                    )

            else:
                raise ActBadResponseError(
                    status_code=status_code,
                    message=f"Response from {self.step_url} missing error code.",
                    raw_response=response.text,
                )

    def _prepare_step_request(
        self, act: Act, observation: BrowserObservation, error_executing_previous_step: Exception | None = None
    ) -> HeliosRequestDict:

        return HeliosRequestDict(
            enableTrace=True,
            nexusActId=act.id,
            nexusSessionId=act.session_id,
            planInput=PlanInputDict(
                planRequest=construct_step_plan_request(act, observation, error_executing_previous_step)
            ),
        )

    def _make_step_request(self, request: HeliosRequestDict) -> Response:

        # Authenticate
        headers = {"Content-Type": "application/json"}
        body = json.dumps(request)
        try:
            headers = self._sign_request("POST", self.step_url, headers, body)
        except Exception as e:
            raise AuthError(self.get_auth_warning_message(f"Authentication error: {str(e)}"))

        # Make request
        return requests.post(
            self.step_url,
            headers=headers,
            data=body,
            timeout=(DEFAULT_REQUEST_CONNECT_TIMEOUT, DEFAULT_REQUEST_READ_TIMEOUT),
        )

    def _sign_request(self, method: str, url: str, headers: dict[str, str], body: str | None = None) -> dict[str, str]:
        """
        Sign a request using SigV4.

        Args:
            method: HTTP method (e.g., 'POST', 'GET')
            url: The endpoint URL
            headers: HTTP headers to include in the request
            body: Request body as a string

        Returns:
            Updated headers dictionary with authentication information

        Raises:
            AWSAuthError: If boto session is not available or credentials are missing
        """
        credentials = self.boto_session.get_credentials()
        if not credentials:
            raise AuthError(self.get_auth_warning_message("AWS credentials not found"))

        aws_request = AWSRequest(method=method, url=url, headers=headers.copy(), data=body)

        signer = botocore.auth.SigV4Auth(credentials, "execute-api", "us-east-1")

        signer.add_auth(aws_request)
        return dict(aws_request.headers)

    def _validate_boto_session(self) -> None:
        """
        Validate that the boto3 session has valid credentials associated with a real IAM identity.

        Args:
            boto_session: The boto3 session to validate

        Raises:
            IAMAuthError: If the boto3 session doesn't have valid credentials or the credentials
                        are not associated with a real IAM identity
        """
        # Check if credentials exist
        try:
            credentials = self.boto_session.get_credentials()
            if not credentials:
                raise IAMAuthError("IAM credentials not found. Please ensure your boto3 session has valid credentials.")
        except Exception as e:
            raise IAMAuthError(f"Failed to get credentials from boto session: {str(e)}")

        # Verify credentials are associated with a real IAM identity
        try:
            sts_client = self.boto_session.client("sts")
            sts_client.get_caller_identity()
        except Exception as e:
            raise IAMAuthError(
                f"IAM validation failed: {str(e)}. Check your credentials with 'aws sts get-caller-identity'."
            )

    def get_auth_warning_message_for_backend(self, message: str) -> str:
        return create_warning_box(
            [
                message,
                "",
                "Please ensure you have received confirmation that your IAM role is allowlisted "
                "and that its policy has the required permissions. ",
                "To join the waitlist, please go here: https://amazonexteu.qualtrics.com/jfe/form/SV_9siTXCFdKHpdwCa",
            ]
        )

    @classmethod
    def get_available_endpoints(cls) -> dict[str, Endpoints]:
        return {
            "helios": Endpoints(api_url="https://helios.nova.amazon.com"),
        }

    @classmethod
    def get_default_endpoints(cls) -> Endpoints:
        return cls.get_available_endpoints()["helios"]
