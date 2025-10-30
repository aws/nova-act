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
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Generic, Optional, TypeVar, cast

from nova_act.impl.interpreter import NovaActInterpreter
from nova_act.impl.program.base import Call, CallResult, Program
from nova_act.tools.actuator.interface.actuator import ActionType
from nova_act.tools.browser.interface.browser import BrowserObservation
from nova_act.types.act_errors import ActBadResponseError, ActInvalidModelGenerationError
from nova_act.types.errors import InterpreterError
from nova_act.types.json_type import JSONType
from nova_act.types.state.act import Act
from nova_act.types.state.step import Step, StepWithProgram
from nova_act.types.workflow_run import WorkflowRun
from nova_act.util.decode_string import decode_string
from nova_act.util.logging import (
    get_session_id_prefix,
    make_trace_logger,
    trace_log_lines,
)

_TRACE_LOGGER = make_trace_logger()

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
    def resolve_endpoints(
        cls,
    ) -> T:

        _endpoints: T = cls.get_default_endpoints()


        return _endpoints

    @classmethod
    @abstractmethod
    def get_available_endpoints(cls) -> Dict[str, T]:
        """
        Return a dictionary of all available endpoints for this backend.

        This method must be implemented by each concrete backend to:
        1. Return all available endpoints configurations as a stage-to-endpoints mapping
        2. Provide a comprehensive dictionary of supported endpoints

        Returns:
            Dictionary mapping backend stage names to Endpoints objects.
        """

    @classmethod
    @abstractmethod
    def get_default_endpoints(cls) -> T:
        """
        Return the default endpoints for this backend.

        This method must be implemented by each concrete backend to return
        the default endpoints when no specific backend stage is requested.

        Returns:
            Default Endpoints object containing the URLs
        """

    @abstractmethod
    def create_session(self, workflow_run: WorkflowRun | None) -> str:
        """Create a session. Must be implemented by concrete backends."""

    @abstractmethod
    def create_act(
        self, workflow_run: WorkflowRun, session_id: str, prompt: str, tools: list[ActionType] | None = None
    ) -> str:
        """Create an act. Must be implemented by concrete backends."""



class AwlBackend(Backend[T]):

    @staticmethod
    def _decode_awl_raw_program(awl_raw_program: str) -> str:
        lines = awl_raw_program.split("\\n")
        decoded_lines = []
        for line in lines:
            decoded_lines.append(decode_string(line))
        awl_program = "\n".join(decoded_lines)
        return awl_program

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
        _TRACE_LOGGER.info(f"{get_session_id_prefix()}...")
        step_object = self.awl_step(act, observation, error_executing_previous_step, call_results)

        # Log it
        awl_program = AwlBackend._decode_awl_raw_program(step_object.model_output.awl_raw_program)
        trace_log_lines(awl_program)

        # Interpret a program from the AST
        try:
            base_program = NovaActInterpreter.interpret_ast(step_object.model_output.program_ast, tool_map)
        except InterpreterError as e:
            # Interpreter received invalid action type or arguments from model
            raise ActInvalidModelGenerationError(
                request_id=step_object.model_output.request_id,
                status_code=200,
                message=str(e),
                raw_response=step_object.model_output.awl_raw_program,
            )
        except ValueError as e:
            # Interpreter received invalid Statements from server
            raise ActBadResponseError(
                request_id=step_object.model_output.request_id,
                status_code=200,
                message=str(e),
                raw_response=json.dumps(step_object.model_output.program_ast),
            )
        calls = base_program.calls

        # Add additional calls as necessary
        if act.observation_delay_ms:
            calls += [Call(name="wait", kwargs={"seconds": act.observation_delay_ms / 1000})]
        calls += [Call(name="waitForPageToSettle", kwargs={}), Call(name="takeObservation", kwargs={})]

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
        """Create a session. Default implementation for all backends."""
        return str(uuid.uuid4())

    def create_act(
        self, workflow_run: WorkflowRun | None, session_id: str, prompt: str, tools: list[ActionType] | None = None
    ) -> str:
        """Create an act. Default implementation for non-workflow backends."""
        return str(uuid.uuid4())

