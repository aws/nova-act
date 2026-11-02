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

from boto3 import Session
from botocore import exceptions as botocore_exceptions
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
from nova_act.types.act_errors import ActServiceUnavailableError
from nova_act.util.logging import setup_logging

_LOGGER = setup_logging(__name__)

DEFAULT_USER_AGENT_EXTRA = f"NovaActSdk/{VERSION}"
# Retry a transient fault once (two total attempts).
_BOTO_TOTAL_MAX_ATTEMPTS = 2
DEFAULT_BOTO_CONFIG = Config(
    retries={"total_max_attempts": _BOTO_TOTAL_MAX_ATTEMPTS, "mode": "standard"},
    read_timeout=60,
    user_agent_extra=DEFAULT_USER_AGENT_EXTRA,
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
        except botocore_exceptions.SSLError:
            raise
        except (botocore_exceptions.ConnectionError, botocore_exceptions.HTTPClientError) as e:
            # botocore's own transient set (connect failures and timeouts, read timeouts, connection
            # resets, broken response streams), minus SSLError, which subclasses ConnectionError.
            raise ActServiceUnavailableError(message=f"Transport error calling Nova Act: {e}") from e

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
