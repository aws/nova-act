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
"""
Helios service client module for Nova Act SDK.

This module handles IAM-based authentication for the Nova Act SDK,
allowing the SDK to make authenticated requests to the Helios service.
"""

import json
from typing import Any, Dict, Tuple

import botocore.auth
import requests
from boto3.session import Session
from botocore.awsrequest import AWSRequest

from nova_act.impl.backend import BackendInfo
from nova_act.impl.helios.errors import (
    handle_error_response,
    handle_http_error,
    has_valid_error_response,
)
from nova_act.impl.helios.types import (
    HeliosRequestDict,
    HeliosResponseDict,
)
from nova_act.impl.helios.validation import (
    validate_helios_response_structure,
    validate_plan_request_structure,
)
from nova_act.types.act_errors import ActBadResponseError
from nova_act.types.act_metadata import ActMetadata
from nova_act.types.errors import IAMAuthError
from nova_act.types.state.act import Act

DEFAULT_REQUEST_CONNECT_TIMEOUT = 30
DEFAULT_REQUEST_READ_TIMEOUT = 5 * 60


class HeliosActServiceClient:
    """
    Handles AWS IAM-based authentication for Nova Act SDK.
    """

    def __init__(self, backend_info: BackendInfo, boto_session: Session | None = None):
        """
        Initialize the HeliosActServiceClient.

        Args:
            boto_session: AWS boto3 session for credentials
            backend_info: BackendInfo object containing API URIs
        """
        self._boto_session = boto_session
        self._backend_info = backend_info
        self._endpoint_url = self._get_endpoint_url()

    def _get_endpoint_url(self) -> str:
        """
        Get the endpoint URL based on backend info.

        Returns:
            The endpoint URL for Helios service
        """
        return f"{self._backend_info.api_uri}/nova-act/invoke"

    def step(
        self,
        plan_request: str,
        act: Act,
        session_id: str,
        metadata: ActMetadata,
    ) -> Tuple[dict | None, str | None, Dict[str, Any]]:
        """
        Execute a step request using Helios service.

        Args:
            plan_request: JSON string containing the actuation plan request
            act: Act object containing information about the current action
            session_id: String identifier for the current session
            metadata: ActMetadata object containing additional metadata

        Returns:
            A tuple containing:
                - The raw program body (str or None if there was an error)
                - A step object (dict) containing input and output information or error object
        """
        headers = {"Content-Type": "application/json"}
        payload = self._create_request_payload(plan_request, act, session_id)
        body = json.dumps(payload)

        try:
            headers = self._sign_request("POST", self._endpoint_url, headers, body)
        except Exception as e:
            raise ActBadResponseError(
                metadata=act.metadata, message=f"Authentication error: {str(e)}", failed_request_id=act.id
            )

        return self._send_request(headers, body, plan_request, act, metadata)

    def _create_request_payload(
        self, plan_request: str, act: Act, session_id: str, enable_trace: bool = True
    ) -> HeliosRequestDict:
        """
        Create the request payload for the Helios service.

        Args:
            plan_request: JSON string containing the actuation plan request
            act: Act object containing information about the current action
            session_id: String identifier for the current session
            enable_trace: Whether to enable tracing in the request

        Returns:
            A dictionary containing the request payload
        """
        plan_request_obj: Dict[str, Any] = json.loads(plan_request)
        validated_plan_request = validate_plan_request_structure(request=plan_request_obj, act=act)

        return {
            "enableTrace": enable_trace,
            "nexusActId": act.id,
            "nexusSessionId": session_id,
            "planInput": {"planRequest": validated_plan_request},
        }

    def _send_request(
        self, headers: Dict[str, str], body: str, plan_request: str, act: Act, metadata: ActMetadata
    ) -> Tuple[dict | None, str | None, Dict[str, Any]]:
        """
        Send a request to the Helios service and process the response.

        Args:
            headers: HTTP headers to include in the request
            body: Request body as a string
            plan_request: Original plan request as a JSON string
            act: Act object containing information about the current action
            metadata: ActMetadata object containing additional metadata

        Returns:
            A tuple containing:
                - The raw program body (str or None if there was an error)
                - A step object (dict) containing input and output information or error object
        """
        response = requests.post(
            self._endpoint_url,
            headers=headers,
            data=body,
            timeout=(DEFAULT_REQUEST_CONNECT_TIMEOUT, DEFAULT_REQUEST_READ_TIMEOUT),
        )

        # Handle HTTP-level errors first
        if response.status_code >= 400:
            return handle_http_error(
                response=response,
                plan_request=plan_request,
                act=act,
                create_step_object_input_func=self._create_step_object_input,
            )

        # Parse JSON for successful HTTP responses
        try:
            json_response = response.json()
        except (json.JSONDecodeError, ValueError) as e:
            raise ActBadResponseError(
                metadata=act.metadata,
                message=f"Invalid JSON in response: {str(e)}. Response content: {response.text}",
                failed_request_id=act.id,
            )

        return self._process_response(json_response=json_response, plan_request=plan_request, act=act)

    def _process_response(
        self, json_response: Dict[str, Any], plan_request: str, act: Act
    ) -> Tuple[dict | None, str | None, Dict[str, Any]]:
        """
        Process the JSON response from the Helios service.

        Args:
            json_response: JSON response from the Helios service
            plan_request: Original plan request as a JSON string
            act: Act object containing information about the current action
            metadata: ActMetadata object containing additional metadata

        Returns:
            A tuple containing:
                - The raw program body (str or None if there was an error)
                - A step object (dict) containing input and output information or error object
        """
        step_object = self._create_step_object_input(plan_request=plan_request, act=act)

        # Check for error response FIRST before validating success structure
        if has_valid_error_response(json_response):
            return handle_error_response(json_response["error"], act)

        # Only validate success structure if no error
        validated_response = validate_helios_response_structure(response=json_response, act=act)
        plan_output = validated_response["planOutput"]
        plan_response = plan_output["planResponse"]
        raw_program_body = plan_response["rawProgramBody"]
        program = plan_response["program"]

        step_object["output"] = plan_response
        self._set_trace_in_step_object(step_object=step_object, validated_response=validated_response)

        return program, raw_program_body, step_object

    def _set_trace_in_step_object(self, step_object: Dict[str, Any], validated_response: HeliosResponseDict) -> None:
        """
        Set trace data in step object if present in response.

        Args:
            step_object: The step object to update
            validated_response: The validated Helios response
        """
        step_object["output"]["trace"] = None
        trace_data = validated_response.get("trace")
        if trace_data:
            step_object["output"]["trace"] = trace_data

    def _create_step_object_input(self, plan_request: str, act: Act) -> Dict[str, Any]:
        """
        Create the input portion of the step object.

        Args:
            plan_request: Original plan request as a JSON string
            act: Act object containing information about the current action

        Returns:
            A dictionary containing the input portion of the step object
        """
        request_object: Dict[str, Any] = json.loads(plan_request)
        step_object: Dict[str, Any] = {
            "input": {
                "screenshot": request_object["screenshotBase64"],
                "prompt": act.prompt,
                "metadata": {"activeUrl": request_object["observation"]["activeURL"]},
                "agentRunCreate": request_object.get("agentRunCreate", {}),
            },
        }

        return step_object

    def _sign_request(self, method: str, url: str, headers: Dict[str, str], body: str | None = None) -> Dict[str, str]:
        """
        Sign a request using SigV4.

        Args:
            method: HTTP method (e.g., 'POST', 'GET')
            url: The endpoint URL
            headers: HTTP headers to include in the request
            body: Request body as a string

        Returns:
            Updated headers dictionary with authentication information

        Raises:
            AWSAuthError: If boto session is not available or credentials are missing
        """
        if not self._boto_session:
            raise IAMAuthError("No boto session available for signing")

        credentials = self._boto_session.get_credentials()
        if not credentials:
            raise IAMAuthError("AWS credentials not found")

        aws_request = AWSRequest(method=method, url=url, headers=headers.copy(), data=body)

        signer = botocore.auth.SigV4Auth(credentials, "execute-api", "us-east-1")

        signer.add_auth(aws_request)
        return dict(aws_request.headers)
