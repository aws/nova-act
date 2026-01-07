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

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, Optional, TypeVar, cast

from nova_act.impl.backends.burst.types import ActErrorData
from nova_act.impl.interpreter import NovaActInterpreter
from nova_act.impl.program.base import Call, CallResult, Program
from nova_act.tools.actuator.interface.actuator import ActionType
from nova_act.tools.browser.interface.browser import BrowserObservation
from nova_act.types.act_errors import ActInvalidModelGenerationError
from nova_act.types.api.status import ActStatus, WorkflowRunStatus
from nova_act.types.errors import InterpreterError
from nova_act.types.json_type import JSONType
from nova_act.types.state.act import Act
from nova_act.types.state.step import Step, StepWithProgram
from nova_act.types.workflow_run import WorkflowRun

T = TypeVar("T", bound="Endpoints")


@dataclass
class Endpoints:
    api_url: str



@dataclass
class ApiKeyEndpoints(Endpoints):
    keygen_url: str
    valid_api_key_length: int = 36




class Backend(ABC, Generic[T]):

    def __init__(
        self,
    ) -> None:
        self.endpoints = self.resolve_endpoints(
        )
        self.validate_auth()

    @staticmethod
    def _maybe_observation(observation: JSONType) -> BrowserObservation:
        # TODO: get rid of BrowserObservation TypedDict && enforce stricter type check with isinstance
        return cast(BrowserObservation, observation)

    @abstractmethod
    def validate_auth(self) -> None:
        """Validates the configurations needed for the given authentication strategy for a concrete backend"""

    @abstractmethod
    def step(self, act: Act, call_results: list[CallResult], tool_map: dict[str, ActionType] = {}) -> StepWithProgram:
        """
        Execute a step using the current route and authentication.

        This method must be implemented by each concrete backend to:
        1. Use the appropriate authentication strategy
        2. Make requests to the correct endpoints
        3. Handle backend-specific request/response processing
        4. Return a Step object with the Program to run

        Args:
            act: The action to execute
            call_results: Results from the Program run after the previous step
            tool_map: Mapping of tool name: callable

        Returns:
            Step object containing the Program to run
        """

    def get_auth_warning_message(self, message: str = "Authentication failed.", request_id: str | None = None) -> str:
        warning = self.get_auth_warning_message_for_backend(message)
        if request_id:
            warning += (
                "\nIf you are sure the above requirements are satisfied and you are still facing AuthError, "
                f"please submit an issue with this request ID: {request_id}"
            )
        return warning

    @abstractmethod
    def get_auth_warning_message_for_backend(self, message: str) -> str:
        """
        Return authentication specific warning for the backend with additional information on
        obtaining credentials.
        """

    @classmethod
    @abstractmethod
    def resolve_endpoints(
        cls,
    ) -> T:
        pass

    @abstractmethod
    def create_session(self, workflow_run: WorkflowRun | None) -> str:
        """Create a session. Must be implemented by concrete backends."""

    @abstractmethod
    def create_act(
        self, workflow_run: WorkflowRun, session_id: str, prompt: str, tools: list[ActionType] | None = None
    ) -> str:
        """Create an act. Must be implemented by concrete backends."""

    @abstractmethod
    def update_act(
        self,
        workflow_run: WorkflowRun | None,
        session_id: str,
        act_id: str,
        status: ActStatus,
        error: ActErrorData | None = None,
    ) -> None:
        """Update an act. Must be implemented by concrete backends."""

    @abstractmethod
    def create_workflow_run(
        self, workflow_definition_name: str, log_group_name: str | None = None, model_id: str = "default"
    ) -> WorkflowRun:
        """Create a workflow run. Must be implemented by concrete backends."""

    @abstractmethod
    def update_workflow_run(self, workflow_run: WorkflowRun | None, status: WorkflowRunStatus) -> None:
        """Update a workflow run. Must be implemented by concrete backends."""


class AwlBackend(Backend[T]):
    """Legacy Backends which pass AWL + AST."""

    def step(self, act: Act, call_results: list[CallResult], tool_map: dict[str, ActionType] = {}) -> StepWithProgram:
        """
        Execute a step with integrated program execution using CallResult interface.

        This is the main step method that combines model communication and program execution:
        1. Extracts observation and error from call_results
        2. Calls awl_step() method to get model response
        3. Internally executes the program using execute_program_step()
        4. Returns a Step with execution_result populated
        5. Throws all execution errors directly (no need for dispatcher to handle them)

        Args:
            act: The action to execute
            call_results: List of CallResult objects containing observation and/or error
            tool_map: Map of tool names to tool functions

        Returns:
            Step object with execution_result populated

        Raises:
            All execution errors are thrown directly from this method
        """
        # Extract observation and error from call_results
        observation: BrowserObservation | None = None
        error_executing_previous_step: Exception | None = None

        for call_result in call_results:
            if call_result.call.name == "takeObservation":
                observation = type(self)._maybe_observation(call_result.return_value)
            elif call_result.error is not None:
                error_executing_previous_step = call_result.error

        if observation is None:
            raise ValueError("No observation found in call_results")

        # Get the step from the model using legacy backends
        step_object = self.awl_step(act, observation, error_executing_previous_step, call_results)

        # Interpret a program from the AST
        try:
            base_program = NovaActInterpreter.interpret_ast(step_object.model_output.program_ast, tool_map)
        except (InterpreterError, ValueError) as e:
            # Interpreter received invalid Statements, action type or arguments from model
            raise ActInvalidModelGenerationError(
                message=str(e), metadata=act.metadata, raw_response=step_object.model_output.awl_raw_program
            )
        calls = base_program.calls

        # Add additional calls as necessary
        if act.observation_delay_ms:
            calls += [Call(name="wait", id="wait", kwargs={"seconds": act.observation_delay_ms / 1000})]
        calls += [
            Call(name="waitForPageToSettle", id="waitForPageToSettle", kwargs={}),
            Call(name="takeObservation", id="takeObservation", kwargs={}),
        ]

        # Return a new Step object with our Program included
        return step_object.with_program(Program(calls=calls))

    @abstractmethod
    def awl_step(
        self,
        act: Act,
        observation: BrowserObservation,
        error_executing_previous_step: Exception | None = None,
        call_results: list[CallResult] | None = None,
    ) -> Step:
        """
        Execute an AWL step using the current route and authentication.

        This method must be implemented by each concrete backend to:
        1. Use the appropriate authentication strategy
        2. Make requests to the correct endpoints
        3. Handle backend-specific request/response processing
        4. Return a Step object with the model response

        Args:
            act: The action to execute
            observation: Current browser observation
            error_executing_previous_step: Optional error from previous step
            call_results: Optional list of previous call results (for tool results)

        Returns:
            Step object containing the model response (without execution)
        """

    def create_session(self, workflow_run: WorkflowRun | None) -> str:
        """Create a session if not exists. Default implementation for all backends."""

        if hasattr(self, "_session_id") and self._session_id is not None:
            return str(self._session_id)

        return str(uuid.uuid4())

    def create_act(
        self, workflow_run: WorkflowRun | None, session_id: str, prompt: str, tools: list[ActionType] | None = None
    ) -> str:
        """Create an act. Default implementation for non-workflow backends."""
        return str(uuid.uuid4())

    def update_act(
        self,
        workflow_run: WorkflowRun | None,
        session_id: str,
        act_id: str,
        status: ActStatus,
        error: ActErrorData | None = None,
    ) -> None:
        """Update an act. Default implementation for non-workflow backends."""
        raise NotImplementedError(f"{self.__class__.__name__} does not support workflow operations")

    def create_workflow_run(
        self, workflow_definition_name: str, log_group_name: str | None = None, model_id: str = "default"
    ) -> WorkflowRun:
        """Create a workflow run. Default implementation for non-workflow backends."""
        raise NotImplementedError(f"{self.__class__.__name__} does not support workflow operations")

    def update_workflow_run(self, workflow_run: WorkflowRun | None, status: WorkflowRunStatus) -> None:
        """Update a workflow run. Default implementation for non-workflow backends."""
        raise NotImplementedError(f"{self.__class__.__name__} does not support workflow operations")
