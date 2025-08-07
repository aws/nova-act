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
Enhanced validation utilities for Helios service client using TypedDict structures.

This module provides TypedDict-based validation functions that offer better
type safety and more detailed error messages compared to basic dict validation.
"""

from typing import Any, Dict, TypeGuard

from nova_act.impl.helios.types import (
    HeliosErrorResponseDict,
    HeliosResponseDict,
    PlanRequestDict,
)
from nova_act.types.act_errors import ActBadResponseError
from nova_act.types.state.act import Act


def is_valid_helios_error_response(data: Dict[str, Any]) -> TypeGuard[HeliosErrorResponseDict]:
    """
    Type guard to validate Helios error response structure.

    Args:
        data: Dictionary to validate

    Returns:
        True if data matches HeliosErrorResponseDict structure, False otherwise
    """
    return (
        isinstance(data, dict)
        and "error" in data
        and isinstance(data["error"], dict)
        and "code" in data["error"]
        and isinstance(data["error"]["code"], str)
        and "message" in data["error"]
        and isinstance(data["error"]["message"], str)
        and data.get("planOutput") is None
    )


def is_valid_plan_request(data: Dict[str, Any]) -> TypeGuard[PlanRequestDict]:
    """
    Type guard to validate plan request structure.

    Args:
        data: Dictionary to validate

    Returns:
        True if data matches PlanRequestDict structure, False otherwise
    """
    return (
        isinstance(data, dict)
        and "screenshotBase64" in data
        and isinstance(data["screenshotBase64"], str)
        and "observation" in data
        and isinstance(data["observation"], dict)
        and "activeURL" in data["observation"]
        and isinstance(data["observation"]["activeURL"], str)
    )


def is_valid_helios_response(data: Dict[str, Any]) -> TypeGuard[HeliosResponseDict]:
    """
    Type guard to validate Helios response structure.

    Args:
        data: Dictionary to validate

    Returns:
        True if data matches HeliosResponseDict structure, False otherwise
    """
    return (
        isinstance(data, dict)
        and "planOutput" in data
        and isinstance(data["planOutput"], dict)
        and "planResponse" in data["planOutput"]
        and isinstance(data["planOutput"]["planResponse"], dict)
        and "rawProgramBody" in data["planOutput"]["planResponse"]
        and isinstance(data["planOutput"]["planResponse"]["rawProgramBody"], str)
    )


def validate_helios_response_structure(response: Dict[str, Any], act: Act) -> HeliosResponseDict:
    """
    Validate and return typed Helios response.

    This function should only be called after confirming there is no error
    in the response, as it validates the success response structure.

    Args:
        response: Raw response from Helios service
        act: Act object for error context

    Returns:
        Validated and typed response

    Raises:
        ActBadResponseError: If response structure is invalid
    """
    if is_valid_helios_response(response):
        return response  # TypeGuard ensures this is now HeliosResponseDict

    # Detailed error messages based on what's missing
    if "planOutput" not in response:
        raise ActBadResponseError(
            metadata=act.metadata,
            message=f"response missing 'planOutput' field\nResponse: {response}",
        )

    plan_output = response.get("planOutput")
    if plan_output is None or not isinstance(plan_output, dict) or "planResponse" not in plan_output:
        raise ActBadResponseError(
            metadata=act.metadata,
            message=f"response missing valid 'planOutput' with 'planResponse' field\nResponse: {response}",
        )

    plan_response = plan_output.get("planResponse", {})
    if "rawProgramBody" not in plan_response:
        raise ActBadResponseError(
            metadata=act.metadata,
            message=f"response missing 'rawProgramBody' field in planResponse\nResponse: {response}",
        )
    if "program" not in plan_response:
        raise ActBadResponseError(
            metadata=act.metadata,
            message=f"response missing 'program' field in planResponse\nResponse: {response}",
        )

    # Generic fallback
    raise ActBadResponseError(
        metadata=act.metadata,
        message=f"Failed to step: invalid response structure\nResponse: {response}",
    )


def validate_plan_request_structure(request: Dict[str, Any], act: Act) -> PlanRequestDict:
    """
    Validate and return typed plan request.

    Args:
        request: Raw plan request dictionary
        act: Act object for error context

    Returns:
        Validated and typed plan request

    Raises:
        ActBadResponseError: If request structure is invalid
    """
    if is_valid_plan_request(request):
        return request  # TypeGuard ensures this is now PlanRequestDict

    # Detailed error messages based on what's missing
    if "screenshotBase64" not in request:
        raise ActBadResponseError(
            metadata=act.metadata,
            message=f"Failed to step: plan request missing 'screenshotBase64' field\nRequest: {request}",
        )

    if "observation" not in request:
        raise ActBadResponseError(
            metadata=act.metadata,
            message=f"Failed to step: plan request missing 'observation' field\nRequest: {request}",
        )

    observation = request.get("observation", {})
    if "activeURL" not in observation:
        raise ActBadResponseError(
            metadata=act.metadata,
            message=f"Failed to step: plan request missing 'activeURL' field in observation\nRequest: {request}",
        )

    # Generic fallback
    raise ActBadResponseError(
        metadata=act.metadata,
        message=f"Failed to step: invalid plan request structure\nRequest: {request}",
    )
