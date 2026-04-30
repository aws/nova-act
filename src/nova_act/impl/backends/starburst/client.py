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
from nova_act.impl.backends.burst.client import BurstClient
from nova_act.impl.backends.burst.errors import NovaActServiceError, translate_nova_act_service_error
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
from nova_act.impl.backends.common import get_client_source
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
    def __init__(
        self,
        boto_session: Session,
        boto_config: Config | None,
    ):
        self._resolve_endpoints(
        )
        self._client_source = get_client_source().value

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

        self._nova_act_client = boto_session.client(service_name="nova-act", endpoint_url=self._api_url, config=config)

        # Add event handler to inject X-Client-Source header
        self._nova_act_client.meta.events.register("before-call", self._add_client_source_header)

    def _resolve_endpoints(
        self,
    ) -> None:
        self._api_url = "https://nova-act.us-east-1.amazonaws.com/"


    def _add_client_source_header(self, params: dict[str, object], **kwargs: object) -> None:
        """Add X-Client-Source header to all requests."""
        if "headers" not in params:
            params["headers"] = {}
        params["headers"]["X-Client-Source"] = self._client_source  # type: ignore[index]

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
        service_error = NovaActServiceError.from_client_error(error)
        return translate_nova_act_service_error(service_error)
