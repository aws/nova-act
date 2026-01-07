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
"""Common utilities shared across backend implementations."""

import json
import os
from enum import Enum

from requests import Response
from typing_extensions import Any

from nova_act.tools.browser.interface.browser import BrowserObservation
from nova_act.types.act_errors import ActBadRequestError, ActBadResponseError, ActInternalServerError
from nova_act.types.api.step import AgentRunCreate, StepPlanRequest
from nova_act.types.state.act import Act

# Request timeout constants
DEFAULT_REQUEST_CONNECT_TIMEOUT = 30  # 30s
DEFAULT_REQUEST_READ_TIMEOUT = 5 * 60  # 5min


def assert_json_response(  # type: ignore[explicit-any]
    response: Response, request_id: str | None = None
) -> dict[str, Any]:
    """Assert that a response contains valid JSON."""
    status_code = response.status_code
    message = f"Received Invalid JSON response from {response.url}"
    raw_response = response.text

    try:
        response = response.json()
    except json.JSONDecodeError:
        # If we receive invalid JSON, we should still indicate if it's a
        # BadResponse, BadRequest, or InternalServerError.

        if status_code < 400:
            raise ActBadResponseError(
                request_id=request_id,
                status_code=status_code,
                message=message,
                raw_response=raw_response,
            )
        elif 400 <= status_code < 500:
            raise ActBadRequestError(
                request_id=request_id,
                status_code=status_code,
                message=message,
                raw_response=raw_response,
            )
        else:
            raise ActInternalServerError(
                request_id=request_id,
                status_code=status_code,
                message=message,
                raw_response=raw_response,
            )

    if not isinstance(response, dict):
        raise ActBadResponseError(
            request_id=request_id,
            status_code=status_code,
            message=message,
            raw_response=raw_response,
        )

    return response


def construct_step_plan_request(
    act: Act, observation: BrowserObservation, error_executing_previous_step: Exception | None
) -> StepPlanRequest:
    """Construct a StepPlanRequest from an Act, Observation, and optional Exception."""

    plan_request: StepPlanRequest = {
        "agentRunId": act.id,
        "idToBboxMap": observation.get("idToBboxMap", {}),
        "observation": {
            "activeURL": observation["activeURL"],
            "browserDimensions": observation["browserDimensions"],
            "idToBboxMap": observation["idToBboxMap"],
            "simplifiedDOM": observation["simplifiedDOM"],
            "timestamp_ms": observation["timestamp_ms"],
            "userAgent": observation["userAgent"],
        },
        "screenshotBase64": observation["screenshotBase64"],
        "tempReturnPlanResponse": True,
    }

    if error_executing_previous_step is not None:
        plan_request["errorExecutingPreviousStep"] = (
            f"{type(error_executing_previous_step).__name__}: {str(error_executing_previous_step)}"
        )

    # If this is the first step, create an agent run
    if not act.steps:
        agent_run_create: AgentRunCreate = {
            "agentConfigName": "plan-v2",
            "id": act.id,
            "plannerFunctionArgs": {"task": act.prompt},
            "plannerFunctionName": "act",
            "task": act.prompt,
        }

        plan_request["agentRunCreate"] = agent_run_create

    return plan_request


class ClientSource(str, Enum):
    """Enumeration of supported client sources."""

    SDK = "sdk"
    EXTENSION = "extension"
    PLAYGROUND = "playground"


def get_client_source() -> ClientSource:
    raw = os.environ.get("NOVA_ACT_CLIENT_SOURCE", ClientSource.SDK.value)
    try:
        return ClientSource(raw)
    except ValueError:
        raise ValueError(f"Invalid NOVA_ACT_CLIENT_SOURCE={raw}. " f"Must be one of {[c.value for c in ClientSource]}")
