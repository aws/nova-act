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
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from botocore.exceptions import ClientError

from nova_act.types.act_errors import (
    ActAPIError,
    ActBadRequestError,
    ActClientError,
    ActDailyQuotaExceededError,
    ActGuardrailsError,
    ActInternalServerError,
    ActInvalidModelGenerationError,
    ActRequestThrottledError,
    ActServerError,
)
from nova_act.types.errors import AuthError


@dataclass
class NovaActServiceError:
    """Normalized representation of a Nova Act service error.

    Acts as an intermediate between backend-specific error types (boto3 `ClientError` for
    Starburst, Coral exceptions for Rainburst) and the SDK's `ActError` hierarchy. Use
    `from_client_error` or `from_coral_exception` to construct, then pass to
    `translate_nova_act_service_error` to obtain the corresponding SDK error.

    Attributes:
        error_code: Service-side exception name (e.g., "ValidationException").
        message: Human-readable error message.
        reason: Sub-classification of the error (e.g., "GuardrailIntervened").
        status_code: HTTP status code from the response, if known.
        raw_response: String representation of the raw error response for debugging.
        request_id: Service request ID for correlation, if available.
        field_list: Per-field validation errors for ValidationException.
        resource_id: Resource identifier for ResourceNotFoundException.
        resource_type: Resource type for ResourceNotFoundException.
        service_code: Service code for ThrottlingException / ServiceQuotaExceededException.
        quota_code: Quota code for ThrottlingException / ServiceQuotaExceededException.
        retry_after_seconds: Retry-After hint from the response, if present.
    """

    error_code: str
    message: str
    reason: str
    status_code: int | None
    raw_response: str
    request_id: str | None = None
    field_list: list[dict[str, str]] = field(default_factory=list)
    resource_id: str = ""
    resource_type: str = ""
    service_code: str = ""
    quota_code: str = ""
    retry_after_seconds: str | None = None


    @classmethod
    def from_client_error(cls, error: ClientError) -> NovaActServiceError:
        """Build a NovaActServiceError from a boto3 ClientError."""

        response = error.response
        error_code = response.get("Error", {}).get("Code", "Unknown")
        metadata = response.get("ResponseMetadata", {})
        field_list_raw = response.get("fieldList", [])
        field_list: list[dict[str, str]] = (
            [
                {"name": str(f.get("name", "")), "message": str(f.get("message", ""))}
                for f in field_list_raw
                if isinstance(f, dict)
            ]
            if isinstance(field_list_raw, list)
            else []
        )

        return cls(
            error_code=error_code,
            message=str(response.get("message", None) or str(error)),
            reason=str(response.get("reason", None) or ""),
            status_code=metadata.get("HTTPStatusCode"),
            raw_response=str(response),
            request_id=metadata.get("RequestId"),
            field_list=field_list,
            resource_id=str(response.get("resourceId", None) or ""),
            resource_type=str(response.get("resourceType", None) or ""),
            service_code=str(response.get("serviceCode", None) or ""),
            quota_code=str(response.get("quotaCode", None) or ""),
            retry_after_seconds=metadata.get("HTTPHeaders", {}).get("Retry-After"),
        )


def translate_nova_act_service_error(error: NovaActServiceError) -> Exception:
    """Translate a NovaActServiceError to the appropriate SDK error type."""
    if error.error_code == "AccessDeniedException":
        return AuthError(f"Access denied: {error.message}")

    elif error.error_code == "ValidationException":
        field_details = ""
        if error.field_list:
            field_details = " Fields: " + ", ".join(
                [f"{f.get('name', '')}: {f.get('message', '')}" for f in error.field_list]
            )
        full_message = f"Validation failed: {error.message}"
        if error.reason:
            full_message += f" (Reason: {error.reason})"
        full_message += field_details

        if error.reason == "GuardrailIntervened":
            return ActGuardrailsError(
                request_id=error.request_id,
                status_code=error.status_code,
                message=full_message,
                raw_response=error.raw_response,
            )

        return ActBadRequestError(
            request_id=error.request_id,
            status_code=error.status_code,
            message=full_message,
            raw_response=error.raw_response,
        )

    elif error.error_code == "ResourceNotFoundException":
        resource_details = ""
        if error.resource_id:
            resource_details += f" Resource ID: {error.resource_id}"
        if error.resource_type:
            resource_details += f" Resource Type: {error.resource_type}"
        full_message = f"Resource not found: {error.message}{resource_details}"
        return ActBadRequestError(
            request_id=error.request_id,
            status_code=error.status_code,
            message=full_message,
            raw_response=error.raw_response,
        )

    elif error.error_code == "ThrottlingException":
        full_message = f"Request throttled: {error.message}"
        if error.service_code:
            full_message += f" Service: {error.service_code}"
        if error.quota_code:
            full_message += f" Quota: {error.quota_code}"
        if error.retry_after_seconds:
            full_message += f" Retry after {error.retry_after_seconds} seconds"

        return ActRequestThrottledError(
            request_id=error.request_id,
            status_code=error.status_code,
            message=full_message,
            raw_response=error.raw_response,
        )

    elif error.error_code == "ServiceQuotaExceededException":
        quota_details = ""
        if error.quota_code:
            quota_details += f" Quota Code: {error.quota_code}"
        if error.service_code:
            quota_details += f" Service: {error.service_code}"
        if error.resource_id:
            quota_details += f" Resource ID: {error.resource_id}"
        if error.resource_type:
            quota_details += f" Resource Type: {error.resource_type}"
        full_message = f"Service quota exceeded: {error.message}{quota_details}"
        return ActDailyQuotaExceededError(
            request_id=error.request_id,
            status_code=error.status_code,
            message=full_message,
            raw_response=error.raw_response,
        )

    elif error.error_code == "InternalServerException":
        if error.reason in ("InvalidModelGeneration", "RequestTokenLimitExceeded"):
            return ActInvalidModelGenerationError(
                message=str(error.message),
                raw_response=error.raw_response,
            )

        full_message = f"Internal server error: {error.message}"
        if error.reason:
            full_message += f" Reason: {error.reason}"
        if error.retry_after_seconds:
            full_message += f" Retry after {error.retry_after_seconds} seconds"
        return ActInternalServerError(
            request_id=error.request_id,
            status_code=error.status_code,
            message=full_message,
            raw_response=error.raw_response,
        )

    else:
        message = f"Unknown error ({error.error_code}): {error.message}"
        if isinstance(error.status_code, int):
            if 500 <= error.status_code < 600:
                return ActServerError(
                    request_id=error.request_id,
                    status_code=error.status_code,
                    message=message,
                    raw_response=error.raw_response,
                )
            elif 400 <= error.status_code < 500:
                return ActClientError(
                    request_id=error.request_id,
                    status_code=error.status_code,
                    message=message,
                    raw_response=error.raw_response,
                )
        return ActAPIError(
            request_id=error.request_id,
            status_code=error.status_code,
            message=message,
            raw_response=error.raw_response,
        )
