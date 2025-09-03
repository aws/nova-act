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
from nova_act.impl.actuation.interface.browser import BrowserObservation
from nova_act.types.api.step import AgentRunCreate, StepRequest


def construct_plan_request(
    act_id: str,
    observation: BrowserObservation,
    prompt: str | None = None,
    error_executing_previous_step: Exception | None = None,
    is_initial_step: bool = False,
    endpoint_name: str | None = None,
) -> StepRequest:

    initial_prompt = prompt
    if not is_initial_step:
        initial_prompt = None

    tempReturnPlanResponse = True

    request_data: StepRequest = {
        "agentRunId": act_id,
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
        "tempReturnPlanResponse": tempReturnPlanResponse,
    }

    if error_executing_previous_step is not None:
        request_data["errorExecutingPreviousStep"] = (
            f"{type(error_executing_previous_step).__name__}: {str(error_executing_previous_step)}"
        )

    agentConfig = "plan-v2"

    if initial_prompt is not None:
        agent_run_create: AgentRunCreate = {
            "agentConfigName": agentConfig,
            "id": act_id,
            "plannerFunctionArgs": {"task": initial_prompt},
            "plannerFunctionName": "act",
            "planningModelServerHost": endpoint_name,
            "task": initial_prompt,
        }

        request_data["agentRunCreate"] = agent_run_create

    return request_data
