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
from typing import Any, Dict

import requests

from nova_act.impl.backend import BackendInfo
from nova_act.types.act_errors import ActInternalServerError, ActProtocolError
from nova_act.types.act_metadata import ActMetadata
from nova_act.types.errors import AuthError, NovaActError
from nova_act.types.state.act import Act

DEFAULT_REQUEST_CONNECT_TIMEOUT = 30  # 30s
DEFAULT_REQUEST_READ_TIMEOUT = 5 * 60  # 5min




class Routes:
    def __init__(
        self,
        backend_info: BackendInfo,
        api_key: str | None,
    ):
        if not api_key:
            raise AuthError(backend_info=backend_info)
        self.backend_info = backend_info
        self.url = backend_info.api_uri + "/step"
        self.auth_header = f"ApiKey {api_key}"


        self.api_key = api_key

    def step(
        self,
        plan_request: str,
        act: Act,
        session_id: str,
        metadata: ActMetadata,
    ) -> tuple[
        str | None,
        dict[str, Any],
    ]:
        """
        Sends an actuation plan request and processes the response.

        Args:
            plan_request: JSON string containing the actuation plan request
            act: Act object containing information about the current action
            session_id: String identifier for the current session
            metadata: ActMetadata object containing additional metadata

        Returns:
            A tuple containing:
                - The raw program body (str or None if there was an error)
                - A step object (dict) containing input and output information or the error object
                if request is not 200 success

        Raises:
            ActProtocolError: If the response is missing expected fields
        """

        request_object: Dict[str, Any] = json.loads(plan_request)
        payload: Dict[str, Any] = {
            "actId": act.id,
            "sessionId": session_id,
            "actuationPlanRequest": plan_request,
        }


        response = requests.post(
            self.url,
            headers={
                "Authorization": self.auth_header,
                "Content-Type": "application/json",
                "X-Api-Key": f"{self.api_key}",
            },
            json=payload,
            timeout=(DEFAULT_REQUEST_CONNECT_TIMEOUT, DEFAULT_REQUEST_READ_TIMEOUT),
        )

        json_response = response.json()

        if response.status_code >= 400:
            error = {
                "type": "NovaActService",
                "code": response.status_code,
                "message": json.dumps({"reason": json_response.get("reason"), "message": json_response.get("fields")}),
            }
            return None, error

        # Construct step object
        input = {
            "screenshot": request_object["screenshotBase64"],
            "prompt": act.prompt,
            "metadata": {"activeUrl": request_object["observation"]["activeURL"]},
        }
        if "agentRunCreate" in request_object:
            input["agentRunCreate"] = request_object["agentRunCreate"]
        step_object = {"input": input, "server_time_s": response.elapsed.total_seconds()}

        if "actuationPlanResponse" not in json_response:
            raise ActProtocolError(
                message=f"Failed to step: {response.text} - response missing actuationPlanResponse", metadata=metadata
            )

        full_response = json.loads(json_response["actuationPlanResponse"])
        if "rawProgramBody" not in full_response:
            raise ActProtocolError(
                message=f"Failed to step: {response.text} - response missing rawProgramBody", metadata=metadata
            )

        step_object["output"] = full_response
        raw_program_body = full_response["rawProgramBody"]

        return raw_program_body, step_object

