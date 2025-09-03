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
from boto3.session import Session
from requests import Response

from nova_act.impl.backend import BackendInfo, is_helios_backend_info
from nova_act.impl.helios.client import HeliosActServiceClient

from nova_act.types.act_errors import ActBadResponseError, ActInternalServerError, ActProtocolError
from nova_act.types.act_metadata import ActMetadata
from nova_act.types.api.step import (
    ParsedStepResponse,
    ProgramErrorResponse,
    StepObject,
    StepObjectInput,
    StepRequest,
)
from nova_act.types.errors import AuthError, NovaActError
from nova_act.types.state.act import Act



DEFAULT_REQUEST_CONNECT_TIMEOUT = 30  # 30s
DEFAULT_REQUEST_READ_TIMEOUT = 5 * 60  # 5min



class Routes:
    """
    Routes class for Nova Act SDK.

    This class is responsible for:
    1. Routing requests to the appropriate service based on authentication method
    2. Processing responses from the service
    3. Handling errors and exceptions
    """

    def __init__(
        self,
        backend_info: BackendInfo,
        api_key: str | None = None,
        boto_session: Session | None = None,
    ):
        """
        Initialize the Routes class.

        Args:
            backend_info: BackendInfo object containing API URIs
            api_key: API key for Sunshine authentication
            use_people_planner: Whether to use people planner
            boto_session: Boto3 session for Moonshine authentication.

        Raises:
            AuthError: If no valid authentication is provided
        """
        self._validate_auth(
            backend_info=backend_info,
            api_key=api_key,
            boto_session=boto_session,
        )

        self.backend_info = backend_info
        self.api_key = api_key
        self._boto_session = boto_session

        self.url = backend_info.api_uri + "/step"
        self.auth_header = f"ApiKey {api_key}" if api_key else None


    def _validate_auth(
        self,
        backend_info: BackendInfo,
        api_key: str | None,
        boto_session: Session | None,
    ) -> None:
        """
        Validate authentication parameters based on backend type.

        Args:
            backend_info: BackendInfo object containing API URIs
            api_key: API key for Sunshine authentication
            boto_session: Boto3 session for Moonshine authentication

        Raises:
            AuthError: If no valid authentication is provided
        """
        # For Helios backends, check if boto_session is provided
        if is_helios_backend_info(backend_info):
            if boto_session is None:
                raise AuthError(backend_info=backend_info)
            return


        if api_key is None:
            raise AuthError(backend_info=backend_info)

    def step(
        self,
        plan_request: StepRequest,
        act: Act,
        session_id: str,
        metadata: ActMetadata,
    ) -> ParsedStepResponse:
        """
        Sends an actuation plan request and processes the response.

        Args:
            plan_request: the actuation plan request
            act: Act object containing information about the current action
            session_id: String identifier for the current session
            metadata: ActMetadata object containing additional metadata

        Returns:
            ParsedStepResponse

        Raises:
            ActProtocolError: If the response is missing expected fields
        """

        # Early routing to Helios service if boto_session is provided
        if self._boto_session:
            service_client = HeliosActServiceClient(backend_info=self.backend_info, boto_session=self._boto_session)
            return service_client.step(
                plan_request=plan_request,
                act=act,
                session_id=session_id,
                metadata=metadata,
            )

        payload: Dict[str, Any] = {
            "actId": act.id,
            "sessionId": session_id,
            "actuationPlanRequest": json.dumps(plan_request),
        }


        response: Response = requests.post(
            self.url,
            headers={
                "Authorization": self.auth_header,
                "Content-Type": "application/json",
                "X-Api-Key": f"{self.api_key}",
            },
            json=payload,
            timeout=(DEFAULT_REQUEST_CONNECT_TIMEOUT, DEFAULT_REQUEST_READ_TIMEOUT),
        )

        return self._post_process_step_response(
            request_object=plan_request,
            response=response,
            act=act,
            metadata=metadata,
        )

    def _post_process_step_response(
        self, request_object: StepRequest, response: Response, act: Act, metadata: ActMetadata
    ) -> ParsedStepResponse:
        request_id = response.headers.get("x-amz-rid", "none")

        error: ProgramErrorResponse
        try:
            json_response = response.json()
        except requests.exceptions.JSONDecodeError:
            error = {
                "type": "NovaActService",
                "code": response.status_code,
                "message": json.dumps({"reason": "Invalid JSON response", "message": response.text}),
                "requestId": request_id,
            }
            return ParsedStepResponse(error=error)

        if response.status_code >= 400:
            error = {
                "type": "NovaActService",
                "code": response.status_code,
                "message": json.dumps({"reason": json_response.get("reason"), "message": json_response.get("fields")}),
                "requestId": request_id,
            }
            return ParsedStepResponse(error=error)

        # Construct step object
        server_time_s = response.elapsed.total_seconds()
        input: StepObjectInput = {
            "screenshot": request_object["screenshotBase64"],
            "prompt": act.prompt,
            "metadata": {"activeURL": request_object["observation"]["activeURL"]},
        }
        if "agentRunCreate" in request_object:
            input["agentRunCreate"] = request_object["agentRunCreate"]

        if "actuationPlanResponse" not in json_response:
            raise ActProtocolError(
                message=f"Failed to step: {response.text} - response missing actuationPlanResponse", metadata=metadata
            )

        full_response = json.loads(json_response["actuationPlanResponse"])
        if "rawProgramBody" not in full_response:
            raise ActProtocolError(
                message=f"Failed to step: {response.text} - response missing rawProgramBody", metadata=metadata
            )
        try:
            program_statements = full_response["program"]["body"][0]["body"]["body"]
        except (IndexError, KeyError, TypeError):
            raise ActProtocolError(
                message=f"Failed to step: {response.text} - response missing program body", metadata=metadata
            )

        return ParsedStepResponse(
            program_statements=program_statements,
            raw_program_body=full_response["rawProgramBody"],
            step_object=StepObject(
                input=input,
                server_time_s=server_time_s,
                output=full_response,
            ),
        )

