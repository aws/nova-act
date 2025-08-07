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
Error handling utilities for Helios service client.

This module provides specialized error handling functions for processing
both HTTP-level errors and Helios-specific error responses, converting
them to the format expected by the protocol layer.
"""

import json
from typing import Any, Callable, Dict, Tuple

import requests

from nova_act.impl.helios.validation import is_valid_helios_error_response
from nova_act.types.act_errors import ActBadResponseError
from nova_act.types.state.act import Act


def has_valid_error_response(json_response: Dict[str, Any]) -> bool:
    """
    Check if the JSON response contains a valid error with a non-empty code.

    Args:
        json_response: JSON response to check

    Returns:
        True if response has error field with non-empty code, False otherwise
    """
    if "error" not in json_response:
        return False

    error = json_response["error"]
    if error is None or not isinstance(error, dict):
        return False

    if "code" not in error:
        return False

    code = error["code"]
    if not code or code == "":
        return False

    return True


def handle_error_response(error_data: Dict[str, Any], act: Act) -> Tuple[None, None, Dict[str, Any]]:
    """
    Convert Helios service error to the format expected by protocol.py.

    Args:
        error_data: Error data from Helios response {"code": "...", "message": "..."}
        act: Act object for error context

    Returns:
        Tuple of (None, error_dict) where error_dict matches protocol expectations
    """
    # Validate error structure using the validation function
    full_error_response = {"planOutput": None, "error": error_data}
    if not is_valid_helios_error_response(full_error_response):
        # Validate required error fields
        for field in ["code", "message"]:
            if not error_data.get(field):
                raise ActBadResponseError(
                    metadata=act.metadata,
                    message=f"Error response missing '{field}' field. Error data: {error_data}",
                    failed_request_id=act.id,
                )

    # Convert to protocol-expected format for string code handling
    error_dict = {
        "type": "NovaActService",
        "code": error_data["code"],  # String code like "INVALID_INPUT"
        "message": error_data["message"],
        "requestId": act.id,
    }
    return None, None, error_dict


def handle_http_error(
    response: requests.Response, plan_request: str, act: Act, create_step_object_input_func: Callable
) -> Tuple[None, None, Dict[str, Any]]:
    """Handle HTTP-level errors from the Helios service."""
    create_step_object_input_func(plan_request, act)

    # Try to parse JSON error response first
    try:
        json_response = response.json()
        if has_valid_error_response(json_response):
            return handle_error_response(error_data=json_response["error"], act=act)
    except (json.JSONDecodeError, ValueError):
        pass

    # Map HTTP status codes to error format expected by protocol.py
    error_dict = map_http_status_to_error(response=response, request_id=act.id)
    return None, None, error_dict


def map_http_status_to_error(response: requests.Response, request_id: str) -> Dict[str, Any]:
    """Map HTTP status codes to the error format expected by protocol.py."""
    status_code = response.status_code

    # Try to extract error details from response body
    try:
        response_json = response.json()
        reason = response_json.get("reason", "HTTP_ERROR")
        message = response_json.get("message", response.text or f"HTTP {status_code} error")
        fields = response_json.get("fields", [])
    except (json.JSONDecodeError, ValueError):
        # Fallback for non-JSON error responses
        reason = "HTTP_ERROR"
        message = response.text or f"HTTP {status_code} error"
        fields = []

    # Create error structure matching protocol format
    error_dict = {
        "type": "NovaActService",
        "code": status_code,  # Integer HTTP status code (not string)
        "message": json.dumps(
            {
                "reason": reason,
                "message": fields if fields else message,
                "http_status": status_code,
                "response_content": str(response.text),
            }
        ),
        "requestId": request_id,
    }

    return error_dict
