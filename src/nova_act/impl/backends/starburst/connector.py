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

from boto3 import Session
from botocore.config import Config
from strands.types.tools import ToolSpec

from nova_act.impl.backends.base import Backend, Endpoints
from nova_act.impl.backends.starburst.types import ActErrorData, Calls
from nova_act.impl.program.base import Call, CallResult, Program
from nova_act.tools.actuator.interface.actuator import ActionType
from nova_act.tools.browser.interface.browser import BrowserObservation
from nova_act.tools.compatibility import safe_tool_spec
from nova_act.types.act_errors import ActError
from nova_act.types.api.status import ActStatus, WorkflowRunStatus
from nova_act.types.errors import IAMAuthError
from nova_act.types.state.act import Act
from nova_act.types.state.step import ModelInput, ModelOutput, StepWithProgram
from nova_act.types.workflow_run import WorkflowRun
from nova_act.util.logging import setup_logging

from .nova_act_client import NovaActClient
from .types import (
    CreateActRequest,
    CreateSessionRequest,
    CreateWorkflowRunRequest,
    InvokeActStepRequest,
    UpdateActRequest,
    UpdateWorkflowRunRequest,
)

_LOGGER = setup_logging(__name__)


class StarburstBackend(Backend[Endpoints]):
    def __init__(
        self,
        boto_session: Session,
        backend_override: str | None = None,
        boto_config: Config | None = None,
    ):
        self.boto_session = boto_session
        super().__init__(
        )
        self._nova_act_client = NovaActClient(boto_session, boto_config, self.endpoints.api_url)

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

    def step(self, act: Act, call_results: list[CallResult], tool_map: dict[str, ActionType] = {}) -> StepWithProgram:
        # Extract observation and error from call_results, similar to base backend
        observation: BrowserObservation | None = None

        for call_result in call_results:
            if call_result.call.name == "takeObservation":
                observation = type(self)._maybe_observation(call_result.return_value)

        if observation is None:
            raise ValueError("No observation found in call_results")

        # Extract workflow context from Act instance
        if not hasattr(act, "workflow_run") or act.workflow_run is None:
            raise ValueError("Act instance must contain workflow_run context for StarburstBackend operations")

        workflow_run = act.workflow_run

        # Extract previous step ID for chaining
        previous_step_id: str | None = None
        if len(act.steps) > 0:
            previous_step_id = act.steps[-1].step_id
            # Validate that previous step has step_id (should not be None for Starburst)
            if previous_step_id is None:
                raise ActError("Missing step_id")

        if len(act.steps) == 0:
            initiate_act_result = CallResult(
                # intiatiateAct is a special call we inject to make the first step request
                # compatible with Starburst backend, and its id is same as its name.
                call=Call(name="initiateAct", id="initiateAct", kwargs={}),
                return_value={},
                error=None,
            )
            # Remove any 'wait' for 'waitForPageToSettle' call results
            call_results = [initiate_act_result, call_results[-1]]

        request = InvokeActStepRequest.from_sdk_data(
            workflow_definition_name=workflow_run.workflow_definition_name,
            workflow_run_id=workflow_run.workflow_run_id,
            session_id=act.session_id,
            act_id=act.id,
            sdk_call_results=call_results,
            previous_step_id=previous_step_id,
        )

        response = self._nova_act_client.invoke_act_step(request)
        awl_program = type(self)._calls_to_awl_program(response.calls)

        return StepWithProgram(
            model_input=ModelInput(
                image=observation["screenshotBase64"],
                prompt=act.prompt,
                active_url=observation["activeURL"],
                simplified_dom=observation["simplifiedDOM"],
            ),
            model_output=ModelOutput(
                awl_raw_program=awl_program or "ERROR: Could not decode model output.",
                request_id=response.get_request_id(),
                program_ast=[],
            ),
            observed_time=datetime.fromtimestamp(time.time(), tz=timezone.utc),
            server_time_s=(
                response.response_metadata.elapsed_time_ms / 1000
                if response.response_metadata.elapsed_time_ms
                else None
            ),
            step_id=response.get_step_id(),
            program=Program(calls=[starburst_call.to_sdk_call() for starburst_call in response.calls]),
        )

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
        return message

    @classmethod
    def resolve_endpoints(
        cls,
        backend_stage: str | None = None,
        backend_api_url_override: str | None = None,
        local_port: int | None = None,
    ) -> Endpoints:
        api_url = "https://nova-act.us-east-1.amazonaws.com/"


        return Endpoints(api_url=api_url)

    def validate_auth(self) -> None:
        self._validate_boto_session()

    def create_act(
        self, workflow_run: WorkflowRun | None, session_id: str, prompt: str, tools: list[ActionType] | None = None
    ) -> str:
        if workflow_run is None:
            raise ValueError("workflow_run parameter is required for StarburstBackend.create_act()")

        tool_specs: list[ToolSpec] = []
        if tools is not None:
            for action_type_tool in tools:
                tool_specs.append(safe_tool_spec(action_type_tool.tool_spec))

        _LOGGER.debug(f"tool_specs length: {len(tool_specs)}")
        _LOGGER.debug(f"tool_specs: {tool_specs}")

        request = CreateActRequest.from_sdk_data(
            workflow_definition_name=workflow_run.workflow_definition_name,
            workflow_run_id=workflow_run.workflow_run_id,
            session_id=session_id,
            task=prompt,
            tool_specs=tool_specs if tool_specs else None,
        )

        response = self._nova_act_client.create_act(request)
        return response.act_id

    def create_session(self, workflow_run: WorkflowRun | None) -> str:
        if workflow_run is None:
            raise ValueError("workflow_run parameter is required for StarburstBackend.create_session()")

        request = CreateSessionRequest.from_sdk_data(
            workflow_definition_name=workflow_run.workflow_definition_name,
            workflow_run_id=workflow_run.workflow_run_id,
        )

        response = self._nova_act_client.create_session(request)
        return response.session_id

    def update_act(
        self,
        workflow_run: WorkflowRun | None,
        session_id: str,
        act_id: str,
        status: ActStatus,
        error: ActErrorData | None = None,
    ) -> str:
        """Update an act with the given status and optional error information."""
        if workflow_run is None:
            raise ValueError("workflow_run parameter is required for StarburstBackend.update_act()")

        request = UpdateActRequest(
            workflow_definition_name=workflow_run.workflow_definition_name,
            workflow_run_id=workflow_run.workflow_run_id,
            session_id=session_id,
            act_id=act_id,
            status=status,
            error=error,
        )
        response = self._nova_act_client.update_act(request)
        return response.get_request_id()

    def create_workflow_run(
        self, workflow_definition_name: str, log_group_name: str | None = None, model_id: str = "nova-act-latest"
    ) -> WorkflowRun:
        """Create a new workflow run and return WorkflowRun DTO."""
        request = CreateWorkflowRunRequest.from_sdk_data(
            workflow_definition_name=workflow_definition_name,
            log_group_name=log_group_name,
            model_id=model_id,
        )
        response = self._nova_act_client.create_workflow_run(request)

        return WorkflowRun(
            workflow_definition_name=workflow_definition_name,
            workflow_run_id=response.workflow_run_id,
        )

    def update_workflow_run(self, workflow_run: WorkflowRun | None, status: WorkflowRunStatus) -> str:
        """Update a workflow run status."""
        if workflow_run is None:
            raise ValueError("workflow_run parameter is required for StarburstBackend.update_workflow_run()")

        request = UpdateWorkflowRunRequest.from_sdk_data(
            workflow_definition_name=workflow_run.workflow_definition_name,
            workflow_run_id=workflow_run.workflow_run_id,
            status=status,
        )
        response = self._nova_act_client.update_workflow_run(request)
        return response.get_request_id()
