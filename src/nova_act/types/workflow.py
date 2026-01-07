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

import functools
import os
from contextvars import ContextVar
from types import MappingProxyType
from typing import Any, Callable, Literal, Type, Union

from boto3 import Session
from botocore.config import Config
from typing_extensions import TypedDict

from nova_act.impl.backends.starburst.backend import StarburstBackend
from nova_act.impl.backends.sunburst.backend import DEFAULT_WORKFLOW_DEFN_NAME, SunburstBackend

from nova_act.types.api.status import WorkflowRunStatus
from nova_act.types.errors import AuthError
from nova_act.types.workflow_run import WorkflowRun
from nova_act.util.constants import NOVA_ACT_AWS_SERVICE, NOVA_ACT_FREE_VERSION
from nova_act.util.error_messages import (
    get_api_key_error_message_for_workflow,
    get_no_authentication_error,
)
from nova_act.util.logging import make_trace_logger, setup_logging

ModelId = Literal["nova-act-latest"]

# Type alias for backends used in Workflow
WorkflowBackend = Union[
    StarburstBackend,
    SunburstBackend,
]  # fmt: skip

_LOGGER = setup_logging(__name__)
_TRACE_LOGGER = make_trace_logger()

FREE_TIER_MESSAGE = (
    f"Running on {NOVA_ACT_FREE_VERSION}. Amazon collects data on interactions on this version. "
    "See more details at nova.amazon.com/act\n"
)
AWS_SERVICE_MESSAGE = f"Running on {NOVA_ACT_AWS_SERVICE}.\n"


class BotoSessionKwargs(TypedDict, total=False):
    """Enforce static typing for kwargs passed to boto3.Session.

    https://boto3.amazonaws.com/v1/documentation/api/latest/reference/core/session.html
    """

    aws_access_key_id: str
    aws_secret_access_key: str
    aws_session_token: str
    region_name: str
    botocore_session: Session
    profile_name: str
    aws_account_id: str


DEFAULT_BOTO_SESSION_KWARGS = MappingProxyType(BotoSessionKwargs(region_name="us-east-1"))


current_workflow: ContextVar[Workflow | None] = ContextVar("current_workflow", default=None)
"""Pointer to current Workflow in this Context."""


def get_current_workflow() -> Workflow | None:
    """Get the current workflow for this Context."""
    return current_workflow.get()


def set_current_workflow(workflow: Workflow | None) -> None:
    """Set the current workflow for this Context"""
    current_workflow.set(workflow)


def workflow(  # type: ignore[explicit-any]
    model_id: ModelId,
    boto_session_kwargs: BotoSessionKwargs | None = None,
    workflow_definition_name: str | None = None,
    boto_config: Config | None = None,
    log_group_name: str | None = None,
    nova_act_api_key: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorate a function to manage it as a NovaAct Workflow.

    This decorator wraps a function to automatically create and manage a Workflow context.
    It handles workflow creation, execution, and cleanup.

    Two authentication methods are supported:
    - boto_session_kwargs: Uses AWS IAM credentials
    - api_key: Uses API key authentication

    Only one authentication method should be provided. If neither is provided, the decorator
    will automatically check for AWS credentials in environment variables (AWS_PROFILE,
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, etc.). If no environment credentials are found,
    a default boto3 Session will be created with us-east-1 region.

    Args:
        model_id: The model ID to use (e.g., "nova-act-latest").
        boto_session_kwargs: Optional kwargs to pass to boto3.Session() for AWS authentication.
            If not provided and no API Key is given, credentials will be automatically loaded
            from environment variables, or default to {"region_name": "us-east-1"}.
        workflow_definition_name: Required when using boto_session_kwargs. The name of the
            workflow definition. When using nova_act_api_key, a default name is used automatically.
        boto_config: Optional botocore Config for the boto3 client.
        log_group_name: Optional CloudWatch log group name for workflow logs. Only supported
            when using boto_session_kwargs.
        nova_act_api_key: Optional API key for authentication. Cannot be used with boto_session_kwargs.

    Returns:
        A decorator function that wraps the target function with Workflow management.

    Example:
        @workflow(
            model_id="nova-act-latest",
            boto_session_kwargs={"region_name": "us-east-1"},
            workflow_definition_name="my-workflow"
        )
        def my_workflow():
            nova = NovaAct(starting_page="https://example.com")
            # ... workflow logic ...
    """

    def decorator(f: Callable[..., Any]) -> Callable[..., Any]:  # type: ignore[explicit-any]
        @functools.wraps(f)
        def wrapper(*args: Any, **kwargs: dict[str, Any]) -> Any:  # type: ignore[explicit-any]
            with Workflow(
                model_id=model_id,
                boto_session_kwargs=boto_session_kwargs,
                workflow_definition_name=workflow_definition_name,
                boto_config=boto_config,
                log_group_name=log_group_name,
                nova_act_api_key=nova_act_api_key,
            ) as workflow:
                outer_workflow = get_current_workflow()
                set_current_workflow(workflow)
                try:
                    return f(*args, **kwargs)
                finally:
                    set_current_workflow(outer_workflow)

        return wrapper

    return decorator


class Workflow:
    """A context manager for executing a NovaAct workflow.

    The Workflow class manages the lifecycle of a NovaAct workflow, including creating
    workflow runs, managing backend connections, and handling authentication.

    Two authentication methods are supported:
    - boto_session_kwargs: Uses AWS IAM credentials
    - nova_act_api_key: Uses API key authentication

    Only one authentication method should be provided. If neither is provided, AWS credentials
    will be automatically loaded from environment variables (AWS_PROFILE, AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY, etc.). If no environment credentials are found, a default boto3
    Session will be created with us-east-1 region.

    Example:
        # Using boto_session_kwargs authentication
        with Workflow(
            model_id="nova-act-latest",
            boto_session_kwargs={"region_name": "us-east-1"},
            workflow_definition_name="my-workflow"
        ) as workflow:
            # ... workflow logic ...

        # Using API key authentication
        with Workflow(
            model_id="nova-act-latest",
            nova_act_api_key="your-api-key",
        ) as workflow:
            # ... workflow logic ...

        # Using environment variables (automatic)
        with Workflow(
            model_id="nova-act-latest",
            workflow_definition_name="my-workflow"
        ) as workflow:
            # Automatically uses AWS_PROFILE or AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY
            # ... workflow logic ...
    """

    def __init__(
        self,
        model_id: ModelId,
        boto_session_kwargs: BotoSessionKwargs | None = None,
        workflow_definition_name: str | None = None,
        boto_config: Config | None = None,
        log_group_name: str | None = None,
        nova_act_api_key: str | None = None,
    ):
        """Initialize a Workflow instance.

        Args:
            model_id: The model ID to use (e.g., "nova-act-latest").
            boto_session_kwargs: Optional kwargs to pass to boto3.Session() for AWS authentication.
                If not provided and no API Key is given, credentials will be automatically loaded
                from environment variables (AWS_PROFILE, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
                etc.), or default to {"region_name": "us-east-1"}.
            workflow_definition_name: Required when using boto_session_kwargs. The name of the
                workflow definition. When using nova_act_api_key, a default name is used automatically.
            boto_config: Optional botocore Config for the boto3 client.
            log_group_name: Optional CloudWatch log group name for workflow logs. Only
                supported when using boto_session_kwargs.
            nova_act_api_key: Optional API key for authentication. Cannot be used with boto_session_kwargs. If used,
                workflow_definition_name is ignored and a default name is used.

        Raises:
            ValueError: If both boto_session_kwargs and nova_act_api_key are provided, or if required
                parameters for the selected authentication method are missing.
        """
        self._workflow_definition_name: str
        self._log_group_name: str | None = log_group_name
        self._backend: WorkflowBackend
        self._model_id = model_id

        # Validate inputs and initialize backend (don't store boto_session/api_key as instance vars)
        self._initialize_backend(
            boto_session_kwargs=boto_session_kwargs,
            nova_act_api_key=nova_act_api_key,
            boto_config=boto_config,
            workflow_definition_name=workflow_definition_name,
        )

        self._workflow_run: WorkflowRun | None = None
        self._managed: bool = False  # Set to True if managed by NovaAct

    def _initialize_backend(
        self,
        boto_session_kwargs: BotoSessionKwargs | None,
        nova_act_api_key: str | None,
        boto_config: Config | None,
        workflow_definition_name: str | None,
    ) -> None:
        """Validate inputs, normalize parameters, and initialize authentication.

        Sets up the appropriate authentication method:
        - If nova_act_api_key is None → creates boto3 Session and uses AWS IAM credentials
        - If nova_act_api_key is provided → uses API key authentication

        When nova_act_api_key is None and boto_session_kwargs is not provided, this method will
        automatically attempt to load AWS credentials from environment variables using
        get_boto_session_kwargs_from_env(). If no environment credentials are found,
        it will fall back to the default boto3 Session configuration.

        Args:
            boto_session_kwargs: Optional kwargs to pass to boto3.Session() for AWS authentication.
            nova_act_api_key: Optional API key for authentication.
            boto_config: botocore Config for the boto3 client.
            workflow_definition_name: Name of the workflow definition.

        Raises:
            ValueError: If both boto_session_kwargs and nova_act_api_key are provided, or if required
                parameters are missing for the selected authentication method.
        """
        # AuthError: Validate that only one authentication method is provided (boto session or API key)
        if boto_session_kwargs is not None and nova_act_api_key is not None:
            raise AuthError("Cannot provide both boto_session_kwargs and nova_act_api_key")

        # Check for authentication when neither is explicitly provided
        if nova_act_api_key is None and boto_session_kwargs is None:
            has_env_api_key: bool = os.environ.get("NOVA_ACT_API_KEY") is not None
            # Check if any AWS credentials are available using boto3
            has_any_aws_credentials: bool = Session().get_credentials() is not None

            # AuthError: Ambiguous authentication when API key exists in env but not explicitly passed
            # In this case, customers may think they are integrating against the AWS Nova Act service,
            # but could accidentally be sending traffic to nova.amazon.com due to the environment-based API key.
            # Customers should either pass the key directly as a function parameter (to use nova.amazon.com) or
            # unset the environment variable (to use AWS service)
            if has_env_api_key:
                raise AuthError(get_api_key_error_message_for_workflow())
            # AuthError: No authentication credentials found (neither API key nor AWS credentials)
            elif not has_any_aws_credentials:
                raise AuthError(get_no_authentication_error())

        if nova_act_api_key is None:
            boto_session: Session = Session(**(boto_session_kwargs or DEFAULT_BOTO_SESSION_KWARGS))
            if workflow_definition_name is None:
                raise ValueError("workflow_definition_name is required in Workflow definition")
            self._workflow_definition_name = workflow_definition_name
            self._backend = StarburstBackend(
                boto_session=boto_session,
                boto_config=boto_config,
            )
            return

        # API key authentication uses default workflow_definition_name and doesn't use log_group_name
        self._workflow_definition_name = DEFAULT_WORKFLOW_DEFN_NAME
        self._backend = SunburstBackend(
            api_key=nova_act_api_key,
        )

    def __enter__(self) -> Workflow:
        """Enter the workflow context and create a workflow run.

        Creates a new workflow run using the configured backend and stores it for
        the duration of the context.

        Returns:
            The Workflow instance.
        """
        # Notify the user as to which backend they are using.
        _TRACE_LOGGER.info(AWS_SERVICE_MESSAGE if isinstance(self._backend, StarburstBackend) else FREE_TIER_MESSAGE)

        # Validation ensures workflow_definition_name and log_group_name are normalized
        self._workflow_run = self._backend.create_workflow_run(
            workflow_definition_name=self._workflow_definition_name,
            log_group_name=self._log_group_name,
            model_id=self._model_id,
        )
        _LOGGER.info(f"Created workflow run {self._workflow_run.workflow_run_id} with model {self._model_id}.")
        return self

    def __exit__(
        self, exc_type: Type[BaseException] | None, exc_value: BaseException | None, traceback: BaseException | None
    ) -> None:
        """Exit the workflow context and update the workflow run status.

        Updates the workflow run status to "SUCCEEDED" if no exception occurred,
        or "FAILED" if an exception was raised during the workflow execution.

        Args:
            exc_type: The exception type if an exception was raised, None otherwise.
            exc_value: The exception instance if an exception was raised, None otherwise.
            traceback: The traceback if an exception was raised, None otherwise.
        """
        try:
            if self._workflow_run is not None:
                # Determine status based on whether an exception occurred
                status: WorkflowRunStatus = "FAILED" if exc_type is not None else "SUCCEEDED"
                self._backend.update_workflow_run(
                    workflow_run=self._workflow_run,
                    status=status,
                )
                _LOGGER.info(f"Updated workflow run {self._workflow_run.workflow_run_id} status to '{status}'")
        finally:
            self._workflow_run = None

    @property
    def workflow_definition_name(self) -> str:
        """Get the workflow definition name.

        Returns:
            The workflow definition name, or None if using API key authentication.
        """
        return self._workflow_definition_name

    @property
    def workflow_run_id(self) -> str:
        """Get the workflow run ID.

        Returns:
            The workflow run ID.

        Raises:
            ValueError: If the workflow has not been started (not in context).
        """
        if self._workflow_run is None:
            raise ValueError("Workflow was not started")
        return self._workflow_run.workflow_run_id

    @property
    def workflow_run(self) -> WorkflowRun | None:
        """Get the WorkflowRun DTO for this workflow.

        Returns:
            The WorkflowRun instance if the workflow is active, None otherwise.
        """
        return self._workflow_run

    @property
    def backend(self) -> WorkflowBackend:
        """Get the workflow backend instance.

        Returns:
            The workflow backend instance.
        """
        return self._backend
