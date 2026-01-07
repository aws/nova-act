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
from abc import abstractmethod
from datetime import datetime, timezone
from typing import TypeVar

from strands.types.tools import ToolSpec

from nova_act.impl.backends.base import Backend, Endpoints
from nova_act.impl.backends.burst.client import BurstClient
from nova_act.impl.backends.burst.types import (
    ActErrorData,
    CallResult,
    Calls,
    CreateActRequest,
    CreateSessionRequest,
    CreateWorkflowRunRequest,
    InvokeActStepRequest,
    UpdateActRequest,
    UpdateWorkflowRunRequest,
)
from nova_act.impl.program.base import Call
from nova_act.impl.program.base import CallResult as SdkCallResult
from nova_act.impl.program.base import Program
from nova_act.tools.actuator.interface.actuator import ActionType
from nova_act.tools.browser.interface.browser import BrowserObservation
from nova_act.tools.compatibility import safe_tool_spec
from nova_act.types.api.status import ActStatus, WorkflowRunStatus
from nova_act.types.state.act import Act
from nova_act.types.state.step import ModelInput, ModelOutput, StepWithProgram
from nova_act.types.workflow_run import WorkflowRun
from nova_act.util.logging import setup_logging

_LOGGER = setup_logging(__name__)
T = TypeVar("T", bound=Endpoints)

S_TO_MS = 1000  # Seconds to milliseconds conversion factor


class BurstBackend(Backend[T]):
    def __init__(
        self,
    ) -> None:
        super().__init__(
        )

        self._client = self._create_client(self.endpoints)

    @abstractmethod
    def _create_client(self, endpoints: T) -> BurstClient:
        """Create a client"""

    @staticmethod
    def _calls_to_awl_program(calls: Calls) -> str:
        """Reverse-engineer an AWL program from Calls."""
        calls_as_awl: list[str] = []
        for call in calls:
            if call.name not in ["initiateAct", "waitForPageToSettle", "takeObservation"]:
                if isinstance(call.input, list):
                    # Actions
                    formatted_input = [f'"{value}"' if isinstance(value, str) else str(value) for value in call.input]
                    calls_as_awl.append(f'{call.name}({", ".join(formatted_input)});')
                elif isinstance(call.input, dict):
                    # Tools
                    calls_as_awl.append(f'tool({{"name": "{call.name}", "input": {json.dumps(call.input)}}});')

        return "\n".join(calls_as_awl)

    def create_act(
        self, workflow_run: WorkflowRun | None, session_id: str, prompt: str, tools: list[ActionType] | None = None
    ) -> str:
        if workflow_run is None:
            raise ValueError(f"workflow_run parameter is required for {type(self).__name__}.create_act(...)")

        tool_specs: list[ToolSpec] = []
        if tools is not None:
            for action_type_tool in tools:
                tool_specs.append(safe_tool_spec(action_type_tool.tool_spec))

        _LOGGER.debug(f"tool_specs length: {len(tool_specs)}")
        _LOGGER.debug(f"tool_specs: {tool_specs}")

        request = CreateActRequest(
            session_id=session_id,
            task=prompt,
            tool_specs=tool_specs or None,
            workflow_definition_name=workflow_run.workflow_definition_name,
            workflow_run_id=workflow_run.workflow_run_id,
        )
        response = self._client.create_act(request)

        return response.act_id

    def create_session(self, workflow_run: WorkflowRun | None) -> str:
        if workflow_run is None:
            raise ValueError(f"workflow_run parameter is required for {type(self).__name__}.create_session(...)")

        request = CreateSessionRequest(
            workflow_definition_name=workflow_run.workflow_definition_name,
            workflow_run_id=workflow_run.workflow_run_id,
        )
        response = self._client.create_session(request)

        return response.session_id

    def create_workflow_run(
        self, workflow_definition_name: str, log_group_name: str | None = None, model_id: str = "nova-act-latest"
    ) -> WorkflowRun:
        """Create a new workflow run and return WorkflowRun DTO."""
        request = CreateWorkflowRunRequest(
            log_group_name=log_group_name,
            model_id=model_id,
            workflow_definition_name=workflow_definition_name,
        )
        response = self._client.create_workflow_run(request)

        return WorkflowRun(
            workflow_definition_name=workflow_definition_name,
            workflow_run_id=response.workflow_run_id,
        )

    def step(
        self, act: Act, call_results: list[SdkCallResult], tool_map: dict[str, ActionType] = {}
    ) -> StepWithProgram:
        # Extract observation and error from call_results, similar to base backend
        observation: BrowserObservation | None = None

        for call_result in call_results:
            if call_result.call.name == "takeObservation":
                observation = type(self)._maybe_observation(call_result.return_value)

        if observation is None:
            raise ValueError("No observation found in call_results")

        # Extract workflow context from Act instance
        if not hasattr(act, "workflow_run") or act.workflow_run is None:
            raise ValueError(f"Act instance must contain workflow_run context for {type(self).__name__}.step(...)")

        workflow_run = act.workflow_run

        previous_step_id: str | None = None
        if len(act.steps) == 0:
            initiate_act_result = SdkCallResult(
                # intiatiateAct is a special call we inject to make the first step request
                # compatible with Starburst backend, and its id is same as its name.
                call=Call(name="initiateAct", id="initiateAct", kwargs={}),
                return_value={},
                error=None,
            )
            # Remove any 'wait' or 'waitForPageToSettle' call results
            call_results = [initiate_act_result, call_results[-1]]
        else:
            previous_step_id = act.steps[-1].step_id

        api_call_result = [CallResult.from_sdk_call_result(sdk_call_result) for sdk_call_result in call_results]
        request = InvokeActStepRequest(
            workflow_definition_name=workflow_run.workflow_definition_name,
            workflow_run_id=workflow_run.workflow_run_id,
            session_id=act.session_id,
            act_id=act.id,
            call_results=api_call_result,
            previous_step_id=previous_step_id,
        )

        start_time = time.perf_counter()
        response = self._client.invoke_act_step(request)
        elapsed_time = time.perf_counter() - start_time

        awl_program = type(self)._calls_to_awl_program(response.calls)
        program = Program(calls=[call.to_sdk_call() for call in response.calls])

        return StepWithProgram(
            model_input=ModelInput(
                image=observation["screenshotBase64"],
                prompt=act.prompt,
                active_url=observation["activeURL"],
                simplified_dom=observation["simplifiedDOM"],
            ),
            model_output=ModelOutput(
                awl_raw_program=awl_program or "ERROR: Could not decode model output.",
                request_id="",
                program_ast=[],
            ),
            observed_time=datetime.now(tz=timezone.utc),
            server_time_s=elapsed_time,
            step_id=response.step_id,
            program=program,
        )

    def update_act(
        self,
        workflow_run: WorkflowRun | None,
        session_id: str,
        act_id: str,
        status: ActStatus,
        error: ActErrorData | None = None,
    ) -> None:
        """Update an act with the given status and optional error information."""
        if workflow_run is None:
            raise ValueError(f"workflow_run parameter is required for {type(self).__name__}.update_act(...)")

        request = UpdateActRequest(
            act_id=act_id,
            error=error,
            session_id=session_id,
            status=status,
            workflow_definition_name=workflow_run.workflow_definition_name,
            workflow_run_id=workflow_run.workflow_run_id,
        )
        self._client.update_act(request)

    def update_workflow_run(self, workflow_run: WorkflowRun | None, status: WorkflowRunStatus) -> None:
        """Update a workflow run status."""
        if workflow_run is None:
            raise ValueError(f"workflow_run parameter is required for {type(self).__name__}.update_workflow_run(...)")

        request = UpdateWorkflowRunRequest(
            status=status,
            workflow_definition_name=workflow_run.workflow_definition_name,
            workflow_run_id=workflow_run.workflow_run_id,
        )
        self._client.update_workflow_run(request)
