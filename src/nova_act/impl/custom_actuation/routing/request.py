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


from nova_act.impl.custom_actuation.interface.browser import BrowserObservation
from nova_act.util.logging import setup_logging

_LOGGER = setup_logging(__name__)



def construct_plan_request(
    act_id: str,
    observation: BrowserObservation,
    prompt: str | None = None,
    error_executing_previous_step: Exception | None = None,
    is_initial_step: bool = False,
    endpoint_name: str | None = None,
) -> str:
    initial_prompt = prompt
    if not is_initial_step:
        initial_prompt = None

    tempReturnPlanResponse = True


    observation_without_screenshot = {k: v for k, v in observation.items() if k != "screenshotBase64"}

    request_data: dict[str, Any] = {
        "agentRunId": act_id,
        "idToBboxMap": observation.get("idToBboxMap", {}),
        "observation": observation_without_screenshot,
        "screenshotBase64": observation["screenshotBase64"],
        "tempReturnPlanResponse": tempReturnPlanResponse,
    }


    if error_executing_previous_step is not None:
        request_data["errorExecutingPreviousStep"] = (
            f"{type(error_executing_previous_step).__name__}: {str(error_executing_previous_step)}"
        )

    agentConfig = "plan-v2"

    if initial_prompt is not None:
        agent_run_create = {
            "agentConfigName": agentConfig,
            "id": act_id,
            "plannerFunctionArgs": {"task": initial_prompt},
            "plannerFunctionName": "act",
            "planningModelServerHost": endpoint_name,
            "task": initial_prompt,
        }


        request_data["agentRunCreate"] = agent_run_create

    string_json_out = json.dumps(request_data)

    return string_json_out


