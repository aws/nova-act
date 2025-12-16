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
import os
import time
from datetime import datetime, timezone
from typing import Final

import requests
from strands.types.tools import ToolSpec

from nova_act.impl.backends.base import ApiKeyEndpoints, Backend
from nova_act.impl.backends.common import assert_json_response
from nova_act.impl.backends.starburst.types import ActErrorData
from nova_act.impl.program.base import Call, CallResult, Program
from nova_act.tools.actuator.interface.actuator import ActionType
from nova_act.tools.browser.interface.browser import BrowserObservation
from nova_act.tools.compatibility import safe_tool_spec
from nova_act.types.act_errors import (
    ActAPIError,
    ActBadRequestError,
    ActClientError,
    ActDailyQuotaExceededError,
    ActGuardrailsError,
    ActInternalServerError,
    ActInvalidModelGenerationError,
    ActRateLimitExceededError,
    ActRequestThrottledError,
    ActServerError,
)
from nova_act.types.errors import AuthError
from nova_act.types.json_type import JSONType
from nova_act.types.state.act import Act
from nova_act.types.state.step import ModelInput, ModelOutput, StepWithProgram
from nova_act.types.workflow_run import WorkflowRun
from nova_act.util.argument_preparation import prepare_kwargs_for_actuation_calls
from nova_act.util.logging import create_warning_box, setup_logging

_LOGGER = setup_logging(__name__)
DEFAULT_WORKFLOW_DEFN_NAME: Final[str] = "default"


class SunburstBackend(Backend[ApiKeyEndpoints]):
    def __init__(
        self,
        api_key: str,
    ):
        self.api_key = api_key
        super().__init__(
        )


    @classmethod
    def resolve_endpoints(
        cls,
    ) -> ApiKeyEndpoints:
        api_url = "https://api.nova.amazon.com"
        keygen_url = "https://nova.amazon.com/dev-apis"


        return ApiKeyEndpoints(api_url=api_url, keygen_url=keygen_url)

    def create_act(
        self, workflow_run: WorkflowRun | None, session_id: str, prompt: str, tools: list[ActionType] | None = None
    ) -> str:
        if workflow_run is None:
            raise ValueError("workflow_run parameter is required for SunburstBackend.create_act()")

        tool_specs: list[ToolSpec] = []
        if tools is not None:
            for action_type_tool in tools:
                tool_specs.append(safe_tool_spec(action_type_tool.tool_spec))

        _LOGGER.debug(f"tool_specs length: {len(tool_specs)}")
        _LOGGER.debug(f"tool_specs: {tool_specs}")

        url: str = (
            f"{self.endpoints.api_url}/agent/workflow-definitions/{workflow_run.workflow_definition_name}"
            f"/workflow-runs/{workflow_run.workflow_run_id}/sessions/{session_id}/acts"
        )
        payload = {
            "task": prompt,
            **({"toolSpecs": tool_specs} if tool_specs else {}),
        }

        response = requests.put(url=url, headers=self._headers, json=payload)
        if response.status_code != requests.codes.created:
            raise type(self)._translate_response_error(response)

        data = response.json()
        act_id: str = data["actId"]
        return act_id

    def create_session(self, workflow_run: WorkflowRun | None) -> str:
        if workflow_run is None:
            raise ValueError("workflow_run parameter is required for SunburstBackend.create_session()")

        url = (
            f"{self.endpoints.api_url}/agent/workflow-definitions/{workflow_run.workflow_definition_name}"
            f"/workflow-runs/{workflow_run.workflow_run_id}/sessions"
        )

        response = requests.put(url=url, headers=self._headers)
        if response.status_code != requests.codes.created:
            raise type(self)._translate_response_error(response)

        data = response.json()
        session_id: str = data["sessionId"]
        return session_id

    def create_workflow_run(
        self,
        workflow_definition_name: str,
        log_group_name: str | None = None,
        model_id: str = "nova-act-latest",
    ) -> WorkflowRun:
        """Create a new workflow run and return WorkflowRun DTO."""
        url = f"{self.endpoints.api_url}/agent/workflow-definitions/{workflow_definition_name}/workflow-runs"
        payload = {"clientInfo": {"compatibilityVersion": 1}, "modelId": model_id}

        response = requests.put(url=url, headers=self._headers, json=payload)
        if response.status_code != requests.codes.created:
            raise type(self)._translate_response_error(response)

        data = response.json()
        return WorkflowRun(
            workflow_definition_name=workflow_definition_name,
            workflow_run_id=data["workflowRunId"],
        )

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
            raise ValueError("Act instance must contain workflow_run context for SunburstBackend operations")

        workflow_run = act.workflow_run

        previous_step_id: str | None = None
        if len(act.steps) == 0:
            initiate_act_result = CallResult(
                call=Call(name="initiateAct", id="initiateAct", kwargs={}), return_value={}, error=None
            )
            # Remove any 'wait' for 'waitForPageToSettle' call results
            call_results = [initiate_act_result, call_results[-1]]
        else:
            previous_step_id = act.steps[-1].step_id

        callResults = []
        for call_result in call_results:
            formatted_return_value = json.dumps(call_result.return_value)
            callResults.append(
                {
                    "callId": call_result.call.id,
                    "content": [
                        {
                            "text": formatted_return_value,
                        }
                    ],
                }
            )

        url = (
            f"{self.endpoints.api_url}/agent/workflow-definitions/{workflow_run.workflow_definition_name}"
            f"/workflow-runs/{workflow_run.workflow_run_id}/sessions/{act.session_id}/acts/{act.id}/invoke-step"
        )
        payload = {
            "callResults": callResults,
            **({"previousStepId": previous_step_id} if previous_step_id else {}),
        }

        response = requests.put(url=url, headers=self._headers, json=payload)
        if response.status_code != requests.codes.ok:
            raise type(self)._translate_response_error(response)

        data = response.json()
        program = type(self)._parse_response_to_program(response)
        awl_program = type(self)._calls_to_awl_program(response)

        return StepWithProgram(
            model_input=ModelInput(
                image=observation["screenshotBase64"],
                prompt=act.prompt,
                active_url=observation["activeURL"],
                simplified_dom=observation["simplifiedDOM"],
            ),
            model_output=ModelOutput(
                awl_raw_program=awl_program or "ERROR: Could not decode model output.",
                request_id=response.headers.get("x-amzn-RequestId", ""),
                program_ast=[],
            ),
            observed_time=datetime.fromtimestamp(time.time(), tz=timezone.utc),
            program=program,
            server_time_s=None,
            step_id=data["stepId"],
        )

    def update_act(
        self,
        workflow_run: WorkflowRun | None,
        session_id: str,
        act_id: str,
        status: str,
        error: ActErrorData | None = None,
    ) -> str:
        if workflow_run is None:
            raise ValueError("workflow_run parameter is required for SunburstBackend.update_act()")

        url = (
            f"{self.endpoints.api_url}/agent/workflow-definitions/{workflow_run.workflow_definition_name}"
            f"/workflow-runs/{workflow_run.workflow_run_id}/sessions/{session_id}/acts/{act_id}"
        )
        payload = {"error": error.model_dump() if error is not None else None, "status": status}

        response = requests.put(url=url, headers=self._headers, json=payload)
        if response.status_code != requests.codes.ok:
            raise type(self)._translate_response_error(response)

        return response.headers.get("x-amzn-RequestId", "")

    def update_workflow_run(self, workflow_run: WorkflowRun | None, status: str) -> str:
        if workflow_run is None:
            raise ValueError("workflow_run parameter is required for SunburstBackend.update_workflow_run()")

        url = (
            f"{self.endpoints.api_url}/agent/workflow-definitions/{workflow_run.workflow_definition_name}"
            f"/workflow-runs/{workflow_run.workflow_run_id}"
        )
        payload = {"status": status}

        response = requests.put(url=url, headers=self._headers, json=payload)
        if response.status_code != requests.codes.ok:
            raise type(self)._translate_response_error(response)

        return response.headers.get("x-amzn-RequestId", "")

    def validate_auth(self) -> None:
        if len(self.api_key) != self.endpoints.valid_api_key_length:
            raise AuthError(self.get_auth_warning_message("Invalid API key length"))

    def get_auth_warning_message_for_backend(self, message: str) -> str:
        return create_warning_box([message, "", f"Please ensure you are using a key from: {self.endpoints.keygen_url}"])

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Api-Key": self.api_key,
        }

    @staticmethod
    def _calls_to_awl_program(response: requests.Response) -> str:
        """Reverse-engineer an AWL program from Sunburst response."""
        data = response.json()
        calls_as_awl: list[str] = []
        for call in data["calls"]:
            call_input = call["input"]
            call_name = call["name"]

            if call_name not in ["initiateAct", "waitForPageToSettle", "takeObservation"]:
                if isinstance(call_input, list):
                    # Actions
                    formatted_input = [f'"{value}"' if isinstance(value, str) else str(value) for value in call_input]
                    calls_as_awl.append(f'{call_name}({", ".join(formatted_input)});')
                elif isinstance(call_input, dict):
                    # Tools
                    calls_as_awl.append(f'tool({{"name": "{call_name}", "input": {json.dumps(call_input)}}});')

        return "\n".join(calls_as_awl)

    @staticmethod
    def _parse_response_to_program(response: requests.Response) -> Program:
        data = response.json()
        sdk_calls = []
        for call in data["calls"]:
            call_id = call["callId"]
            input = call["input"]
            name = call["name"]

            if isinstance(input, dict):
                kwargs: dict[str, JSONType] = input
                is_tool = True
            else:
                kwargs = prepare_kwargs_for_actuation_calls(name, input)
                is_tool = False

            sdk_call = Call(name=name, kwargs=kwargs, id=call_id, is_tool=is_tool)
            sdk_calls.append(sdk_call)

        program = Program(calls=sdk_calls)
        return program

    @staticmethod
    def _translate_response_error(response: requests.Response) -> Exception:
        request_id = response.headers.get("x-amzn-RequestId", "")
        status_code = response.status_code

        try:
            data = assert_json_response(response, request_id)
        except Exception as e:
            return e

        if status_code == requests.codes.bad_request:
            message = f"Validation failed: {data.get('message', '')}"
            reason = data.get("reason")
            if reason == "AGENT_GUARDRAILS_TRIGGERED":
                return ActGuardrailsError(
                    message=message + f" Reason: {reason}",
                    raw_response=response.text,
                    request_id=request_id,
                    status_code=status_code,
                )
            elif reason == "INVALID_INPUT":
                fields = data.get("fields")
                fields_str = ""
                if isinstance(fields, list):
                    fields_str = " Fields: " + ", ".join(
                        [f"{f.get('name', '')}: {f.get('message', '')}" for f in fields if isinstance(f, dict)]
                    )
                return ActBadRequestError(
                    message=message + f" Reason: {reason}" + fields_str,
                    raw_response=response.text,
                    request_id=request_id,
                    status_code=status_code,
                )

            return ActBadRequestError(
                message=message,
                raw_response=response.text,
                request_id=request_id,
                status_code=status_code,
            )

        elif status_code == requests.codes.not_found:
            message = (
                f"Resource not found: {data.get('message', '')}"
                f" Resource ID: {data.get('resourceId', '')}"
                f" Resource Type: {data.get('resourceType', '')}"
            )
            return ActBadRequestError(
                message=message,
                raw_response=response.text,
                request_id=request_id,
                status_code=status_code,
            )

        elif status_code == requests.codes.too_many_requests:
            message = f"Request throttled: {data.get('message', '')}"
            throttle_type = data.get("throttleType")
            if throttle_type == "DAILY_QUOTA_LIMIT_EXCEEDED":
                return ActDailyQuotaExceededError(
                    message=message + f" Throttle Type: {throttle_type}",
                    raw_response=response.text,
                    request_id=request_id,
                    status_code=status_code,
                )
            elif throttle_type == "RATE_LIMIT_EXCEEDED":
                return ActRateLimitExceededError(
                    message=message + f" Throttle Type: {throttle_type}",
                    raw_response=response.text,
                    request_id=request_id,
                    status_code=status_code,
                )

            return ActRequestThrottledError(
                message=message,
                raw_response=response.text,
                request_id=request_id,
                status_code=status_code,
            )

        elif status_code == requests.codes.internal_server_error:
            reason = data.get("reason")
            message = f"Internal server error: {data.get('message', '')}" + (f" Reason: {reason}" if reason else "")
            if reason == "InvalidModelGeneration":
                return ActInvalidModelGenerationError(
                    message=message,
                    raw_response=response.text,
                )

            return ActInternalServerError(
                message=message,
                raw_response=response.text,
                request_id=request_id,
                status_code=status_code,
            )

        message = f"Unknown error: {data.get('message', '')}"
        # If we have an HTTP status code, group unknown errors as Server/Client
        if isinstance(status_code, int):
            if 500 <= status_code < 600:
                return ActServerError(
                    request_id=request_id,
                    status_code=status_code,
                    message=message,
                    raw_response=response.text,
                )
            elif 400 <= status_code < 500:
                return ActClientError(
                    request_id=request_id,
                    status_code=status_code,
                    message=message,
                    raw_response=response.text,
                )
        # Otherwise, default to generic ActAPIError for unknown error types
        return ActAPIError(
            message=message,
            raw_response=response.text,
            request_id=request_id,
            status_code=status_code,
        )
