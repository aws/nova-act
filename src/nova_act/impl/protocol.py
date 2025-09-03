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
from enum import Enum
from typing import Any

from nova_act.impl.backend import BackendInfo
from nova_act.types.act_errors import (
    ActActuationError,
    ActBadRequestError,
    ActBadResponseError,
    ActError,
    ActExceededMaxStepsError,
    ActGuardrailsError,
    ActInternalServerError,
    ActInvalidInputError,
    ActModelError,
    ActNotAuthorizedError,
    ActProtocolError,
    ActRateLimitExceededError,
    ActServiceUnavailableError,
)
from nova_act.types.api.step import ProgramErrorResponse
from nova_act.types.errors import AuthError
from nova_act.types.state.act import Act

NOVA_ACT_SERVICE = "NovaActService"
NOVA_ACT_CLIENT = "NovaActClient"


class NovaActClientErrors(Enum):
    BAD_RESPONSE = "BAD_RESPONSE"
    MAX_STEPS_EXCEEDED = "MAX_STEPS_EXCEEDED"
    ACTUATION_ERROR = "ACTUATION_ERROR"
    INTERPRETATION_ERROR = "INTERPRETATION_ERROR"


class NovaActServiceError(Enum):
    INVALID_INPUT = "INVALID_INPUT"
    MODEL_ERROR = "MODEL_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    GUARDRAILS_ERROR = "GUARDRAILS_ERROR"
    UNAUTHORIZED_ERROR = "UNAUTHORIZED_ERROR"
    TOO_MANY_REQUESTS = "TOO_MANY_REQUESTS"
    DAILY_QUOTA_LIMIT_ERROR = "DAILY_QUOTA_LIMIT_ERROR"


def handle_nova_act_service_error(error: ProgramErrorResponse, act: Act, backend_info: BackendInfo) -> ActError:
    request_id = error.get("requestId", "")
    code = error.get("code")
    message = error.get("message")

    if isinstance(code, str):
        act_error = _handle_service_error_with_string_code(error, act)
        return act_error

    if not isinstance(code, int) or code == -1:
        return ActProtocolError(
            metadata=act.metadata,
            message="invalid error code in Server Response: " + json.dumps(error),
            failed_request_id=request_id,
        )

    if 400 == code:
        error_dict = check_error_is_json(message)
        if not isinstance(error_dict, dict):
            return ActBadRequestError(metadata=act.metadata, failed_request_id=request_id, message=json.dumps(error))

        if "AGENT_GUARDRAILS_TRIGGERED" == error_dict.get("reason"):
            return ActGuardrailsError(message=error_dict, metadata=act.metadata)
        if "INVALID_INPUT" == error_dict.get("reason"):
            return ActInvalidInputError(metadata=act.metadata)
        if "MODEL_ERROR" == error_dict.get("reason"):
            return ActModelError(message=error_dict, metadata=act.metadata)
    if 403 == code:
        raise AuthError(backend_info, request_id=request_id)
    if 429 == code:
        maybe_error_dict = check_error_is_json(message)
        return ActRateLimitExceededError(
            message=maybe_error_dict if isinstance(maybe_error_dict, dict) else {"message": message},
            metadata=act.metadata,
            failed_request_id=request_id,
        )
    # 4xx
    if code < 500 and code >= 400:
        return ActBadRequestError(metadata=act.metadata, failed_request_id=request_id, message=json.dumps(error))
    if 503 == code:
        return ActServiceUnavailableError(
            metadata=act.metadata, failed_request_id=request_id, message=json.dumps(error)
        )
    # 5xx
    if code < 600 and code >= 500:
        return ActInternalServerError(metadata=act.metadata, failed_request_id=request_id, message=json.dumps(error))

    return ActProtocolError(
        message="Unhandled NovaActService error: " + json.dumps(error),
        metadata=act.metadata,
        failed_request_id=request_id,
    )


def handle_nova_act_client_error(error: ProgramErrorResponse, act: Act) -> ActError:
    request_id = error.get("requestId", "")
    code = str(error.get("code", ""))

    try:
        error_type = NovaActClientErrors[code]
    except (KeyError, TypeError, ValueError, IndexError) as e:
        return ActProtocolError(
            message="invalid NovaActClient error code: " + json.dumps(error) + "; " + str(e),
            metadata=act.metadata,
            failed_request_id=request_id,
        )

    if error_type == NovaActClientErrors.BAD_RESPONSE:
        return ActBadResponseError(metadata=act.metadata, failed_request_id=request_id, message=json.dumps(error))
    if error_type == NovaActClientErrors.MAX_STEPS_EXCEEDED:
        return ActExceededMaxStepsError(metadata=act.metadata)
    if error_type == NovaActClientErrors.ACTUATION_ERROR:
        return ActActuationError(
            metadata=act.metadata, message=error.get("message", ""), exception=error.get("exception", None)
        )
    if error_type == NovaActClientErrors.INTERPRETATION_ERROR:
        return ActModelError(metadata=act.metadata, message=dict(error))

    return ActProtocolError(
        message="Unhandled NovaActClient error: " + json.dumps(error),
        metadata=act.metadata,
        failed_request_id=request_id,
    )


def check_error_is_json(message: Any) -> Any:
    try:
        return json.loads(message)
    except (json.JSONDecodeError, TypeError):
        return None


def _handle_service_error_with_string_code(error: ProgramErrorResponse, act: Act) -> ActError:
    """Translates errors returned by Nova Act backends that return string error codes."""
    code = str(error.get("code") or "")
    message: str | None = error.get("message")

    try:
        error_type = NovaActServiceError[code]
    except (KeyError, TypeError, ValueError, IndexError):
        return ActProtocolError(
            message=f"invalid NovaActService error code: {code}",
            metadata=act.metadata,
        )

    if error_type == NovaActServiceError.INVALID_INPUT:
        return ActInvalidInputError(message=message, metadata=act.metadata)

    if error_type == NovaActServiceError.INTERNAL_ERROR:
        return ActInternalServerError(message=message, metadata=act.metadata)

    if error_type == NovaActServiceError.UNAUTHORIZED_ERROR:
        return ActNotAuthorizedError(
            message="Access denied. To request access, email nova-act@amazon.com with your use case.",
            metadata=act.metadata,
        )

    if error_type == NovaActServiceError.MODEL_ERROR:
        message_fields = {"fields": [{"message": message}]}
        return ActModelError(message=message_fields, metadata=act.metadata)

    if error_type == NovaActServiceError.GUARDRAILS_ERROR:
        message_fields = {"fields": [{"message": message}]}
        return ActGuardrailsError(message=message_fields, metadata=act.metadata)

    if error_type == NovaActServiceError.TOO_MANY_REQUESTS:
        message_dict = {"throttleType": "RATE_LIMIT_EXCEEDED", "message": message}
        return ActRateLimitExceededError(message=message_dict, metadata=act.metadata)

    if error_type == NovaActServiceError.DAILY_QUOTA_LIMIT_ERROR:
        message_dict = {"throttleType": "DAILY_QUOTA_LIMIT_EXCEEDED", "message": message}
        return ActRateLimitExceededError(message=message_dict, metadata=act.metadata)

    return ActProtocolError(
        message=f"Unhandled NovaActService error: {code}",
        metadata=act.metadata,
    )
