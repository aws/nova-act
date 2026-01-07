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
from copy import deepcopy
from typing import Literal, TypedDict

from boto3 import Session
from botocore.config import Config
from botocore.exceptions import ClientError

from nova_act.__version__ import VERSION
from nova_act.impl.backends.base import Endpoints
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
from nova_act.types.act_errors import (
    ActAPIError,
    ActBadRequestError,
    ActClientError,
    ActDailyQuotaExceededError,
    ActGuardrailsError,
    ActInternalServerError,
    ActInvalidModelGenerationError,
    ActRequestThrottledError,
    ActServerError,
)
from nova_act.types.errors import AuthError
from nova_act.util.logging import setup_logging

_LOGGER = setup_logging(__name__)

SERVICE_MODEL_DEFAULT_RETRIES = 4
DEFAULT_USER_AGENT_EXTRA = f"NovaActSdk/{VERSION}"
DEFAULT_BOTO_CONFIG = Config(
    retries={"total_max_attempts": 2, "mode": "standard"}, read_timeout=60, user_agent_extra=DEFAULT_USER_AGENT_EXTRA
)


class _RetriesConfig(TypedDict, total=False):
    """Type-safe Config.retries.

    The attribute is added dynamically, so mypy does not recognize Config.retries.
    Create an internal Type to handle this.

    """

    total_max_attempts: int
    max_attempts: int
    strategy: Literal["legacy", "standard", "adaptive"]


def _validate_retries(config: Config) -> None:
    """Warn if client configures > 1 total retry.

    Botocore retry [documentation](https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html):

    retries (dict) -
    A dictionary for configuration related to retry behavior. Valid keys are:
    * `total_max_attempts` - An integer representing the maximum number of total attempts that will be made on a
      single request. This includes the initial request, so a value of 1 indicates that no requests will be retried.
      If total_max_attempts and max_attempts are both provided, total_max_attempts takes precedence. total_max_attempts
      is preferred over max_attempts because it maps to the AWS_MAX_ATTEMPTS environment variable and the max_attempts
      config file value.
    * `max_attempts` - An integer representing the maximum number of retry attempts that will be made on a single
      request. For example, setting this value to 2 will result in the request being retried at most two times after
      the initial request. Setting this value to 0 will result in no retries ever being attempted after the initial
      request. If not provided, the number of retries will default to the value specified in the service model, which
      is typically four retries.
    * `mode` - A string representing the type of retry mode botocore should use. Valid values are:
      * `legacy` - The pre-existing retry behavior.
      * `standard` - The standardized set of retry rules. This will also default to 3 max attempts unless overridden.
      * `adaptive` - Retries with additional client side throttling.

    """
    config_retries: _RetriesConfig = config.retries  # type: ignore[attr-defined]
    if not config_retries:
        retries = SERVICE_MODEL_DEFAULT_RETRIES
    else:
        if (_retries := config_retries.get("total_max_attempts")) is not None:
            retries = _retries - 1
        elif (_retries := config_retries.get("max_attempts")) is not None:
            retries = _retries
        elif config_retries.get("mode") == "standard":
            retries = 3
        else:
            retries = SERVICE_MODEL_DEFAULT_RETRIES

    if retries > 1:
        _LOGGER.warning(
            "Configuring NovaAct with >1 retry might result in service throttling. "
            "We recommend total_max_attempts == 2."
        )


def _validate_timeout(config: Config) -> None:
    """Warn if client configures <=50s read_timeout."""
    if config.read_timeout <= 50:  # type: ignore[attr-defined]
        _LOGGER.warning(
            "Configuring NovaAct with <=50s read_timeout might result in service throttling. "
            "We recommend read_timeout >= 60s."
        )


def _validate_user_agent_extra(config: Config) -> None:
    """Warn if Config has user_agent_extra set."""
    if (user_agent_extra := config.user_agent_extra) != DEFAULT_USER_AGENT_EXTRA:  # type: ignore[attr-defined]
        _LOGGER.warning(
            f"NovaAct requires a specific user_agent_extra; value '{user_agent_extra}' "
            f"will be overridden with '{DEFAULT_USER_AGENT_EXTRA}'."
        )


class StarburstClient(BurstClient):
    def __init__(self, endpoints: Endpoints, boto_session: Session, boto_config: Config | None):
        self._endpoints = endpoints

        if boto_config is not None:
            config = deepcopy(boto_config)
        else:
            config = DEFAULT_BOTO_CONFIG

        # Warn for dangerous boto config values
        _validate_retries(config)
        _validate_timeout(config)
        _validate_user_agent_extra(config)

        # Set correct user_agent_extra
        config.user_agent_extra = DEFAULT_USER_AGENT_EXTRA  # type: ignore[attr-defined]

        self._nova_act_client = boto_session.client(
            service_name="nova-act", endpoint_url=endpoints.api_url, config=config
        )

    def create_act(self, request: CreateActRequest) -> CreateActResponse:
        """Create an act with type-safe request/response."""
        try:
            params = request.model_dump(by_alias=True, exclude_none=True)
            response = self._nova_act_client.create_act(**params)
            return CreateActResponse.model_validate(response)
        except ClientError as e:
            raise type(self)._translate_client_error(e)

    def create_session(self, request: CreateSessionRequest) -> CreateSessionResponse:
        """Create a session with type-safe request/response."""
        try:
            params = request.model_dump(by_alias=True, exclude_none=True)
            response = self._nova_act_client.create_session(**params)
            return CreateSessionResponse.model_validate(response)
        except ClientError as e:
            raise type(self)._translate_client_error(e)

    def create_workflow_run(self, request: CreateWorkflowRunRequest) -> CreateWorkflowRunResponse:
        """Create a workflow run with type-safe request/response."""
        try:
            params = request.model_dump(by_alias=True, exclude_none=True)
            response = self._nova_act_client.create_workflow_run(**params)
            return CreateWorkflowRunResponse.model_validate(response)
        except ClientError as e:
            raise type(self)._translate_client_error(e)

    def invoke_act_step(self, request: InvokeActStepRequest) -> InvokeActStepResponse:
        """Invoke an act step with type-safe request/response."""
        try:
            params = request.model_dump(by_alias=True, exclude_none=True)
            response = self._nova_act_client.invoke_act_step(**params)
            return InvokeActStepResponse.model_validate(response)
        except ClientError as e:
            raise type(self)._translate_client_error(e)

    def update_act(self, request: UpdateActRequest) -> UpdateActResponse:
        """Update an act with type-safe request/response."""
        try:
            params = request.model_dump(by_alias=True, exclude_none=True)
            response = self._nova_act_client.update_act(**params)
            return UpdateActResponse.model_validate(response)
        except ClientError as e:
            raise type(self)._translate_client_error(e)

    def update_workflow_run(self, request: UpdateWorkflowRunRequest) -> UpdateWorkflowRunResponse:
        """Update a workflow run with type-safe request/response."""
        try:
            params = request.model_dump(by_alias=True, exclude_none=True)
            response = self._nova_act_client.update_workflow_run(**params)
            return UpdateWorkflowRunResponse.model_validate(response)
        except ClientError as e:
            raise type(self)._translate_client_error(e)

    @staticmethod
    def _translate_client_error(error: ClientError) -> Exception:
        """Translate boto3 ClientError to appropriate SDK error type."""

        raw_response = str(error.response)
        error_code = error.response.get("Error", {}).get("Code", "Unknown")
        error_message = error.response.get("message", str(error))
        error_reason = error.response.get("reason", "")

        request_id = error.response.get("ResponseMetadata", {}).get("RequestId")
        status_code = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")

        if error_code == "AccessDeniedException":
            return AuthError(f"Access denied: {error_message}")

        elif error_code == "ValidationException":
            # Include field details if available
            field_list = error.response.get("fieldList", [])
            field_details = ""
            if field_list and isinstance(field_list, list):
                field_details = " Fields: " + ", ".join(
                    [f"{f.get('name', '')}: {f.get('message', '')}" for f in field_list if isinstance(f, dict)]
                )
            full_message = f"Validation failed: {error_message}"
            if error_reason:
                full_message += f" (Reason: {error_reason})"
            full_message += field_details

            if "GuardrailIntervened" == error_reason:
                return ActGuardrailsError(
                    request_id=request_id,
                    status_code=status_code,
                    message=full_message,
                    raw_response=raw_response,
                )

            return ActBadRequestError(
                request_id=request_id,
                status_code=status_code,
                message=full_message,
                raw_response=raw_response,
            )

        elif error_code == "ResourceNotFoundException":
            # Include resource details if available
            resource_id = error.response.get("resourceId", "")
            resource_type = error.response.get("resourceType", "")
            resource_details = ""
            if resource_id:
                resource_details += f" Resource ID: {resource_id}"
            if resource_type:
                resource_details += f" Resource Type: {resource_type}"
            full_message = f"Resource not found: {error_message}{resource_details}"
            return ActBadRequestError(
                request_id=request_id,
                status_code=status_code,
                message=full_message,
                raw_response=raw_response,
            )

        elif error_code == "ThrottlingException":
            # Extract structured fields from error response
            service_code = error.response.get("serviceCode", "")
            quota_code = error.response.get("quotaCode", "")
            # retryAfterSeconds is in HTTP headers per service model
            retry_after_seconds = error.response.get("ResponseMetadata", {}).get("HTTPHeaders", {}).get("Retry-After")

            # Build comprehensive message
            full_message = f"Request throttled: {error_message}"

            if service_code:
                full_message += f" Service: {service_code}"
            if quota_code:
                full_message += f" Quota: {quota_code}"
            if retry_after_seconds:
                full_message += f" Retry after {retry_after_seconds} seconds"

            return ActRequestThrottledError(
                request_id=request_id,
                status_code=status_code,
                message=full_message,
                raw_response=raw_response,
            )

        elif error_code == "ServiceQuotaExceededException":
            # Include quota details if available
            quota_code = error.response.get("quotaCode", "")
            service_code = error.response.get("serviceCode", "")
            resource_id = error.response.get("resourceId", "")
            resource_type = error.response.get("resourceType", "")
            quota_details = ""
            if quota_code:
                quota_details += f" Quota Code: {quota_code}"
            if service_code:
                quota_details += f" Service: {service_code}"
            if resource_id:
                quota_details += f" Resource ID: {resource_id}"
            if resource_type:
                quota_details += f" Resource Type: {resource_type}"
            full_message = f"Service quota exceeded: {error_message}{quota_details}"
            return ActDailyQuotaExceededError(
                request_id=request_id,
                status_code=status_code,
                message=full_message,
                raw_response=raw_response,
            )

        elif error_code == "InternalServerException":
            # Check if this is an InvalidModelGeneration error
            if error_reason == "InvalidModelGeneration":
                return ActInvalidModelGenerationError(
                    message=str(error_message),
                    raw_response=raw_response,
                )

            # Include retry information and reason if available
            retry_after = error.response.get("ResponseMetadata", {}).get("HTTPHeaders", {}).get("Retry-After")
            full_message = f"Internal server error: {error_message}"
            if error_reason:
                full_message += f" Reason: {error_reason}"
            if retry_after:
                full_message += f" Retry after {retry_after} seconds"
            return ActInternalServerError(
                request_id=request_id,
                status_code=status_code,
                message=full_message,
                raw_response=raw_response,
            )

        else:
            message = f"Unknown error ({error_code}): {error_message}"
            # If we have an HTTP status code, group unknown errors as Server/Client
            if isinstance(status_code, int):
                if 500 <= status_code < 600:
                    return ActServerError(
                        request_id=request_id,
                        status_code=status_code,
                        message=message,
                        raw_response=raw_response,
                    )
                elif 400 <= status_code < 500:
                    return ActClientError(
                        request_id=request_id,
                        status_code=status_code,
                        message=message,
                        raw_response=raw_response,
                    )
            # Otherwise, default to generic ActAPIError for unknown error types
            return ActAPIError(
                request_id=request_id,
                status_code=status_code,
                message=message,
                raw_response=raw_response,
            )
