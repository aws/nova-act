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
from typing import Any, cast

from nova_act.impl.backend import BackendInfo
from nova_act.types.act_errors import (
    ActAgentError,
    ActBadRequestError,
    ActBadResponseError,
    ActCanceledError,
    ActExceededMaxStepsError,
    ActGuardrailsError,
    ActInternalServerError,
    ActInvalidInputError,
    ActModelError,
    ActProtocolError,
    ActRateLimitExceededError,
    ActServiceUnavailableError,
    ActTimeoutError,
)
from nova_act.types.errors import AuthError
from nova_act.types.state.act import Act, ActFailed

NOVA_ACT_SERVICE = "NovaActService"
NOVA_ACT_CLIENT = "NovaActClient"


class NovaActClientErrors(Enum):
    BAD_RESPONSE = "BAD_RESPONSE"
    MAX_STEPS_EXCEEDED = "MAX_STEPS_EXCEEDED"


def parse_errors(act: Act, backend_info: BackendInfo):
    if not isinstance(act.result, ActFailed) or not act.is_complete:
        raise ValueError(f"Expected ActFailed result when attempting to parse, got act: {act}")

    result = cast(ActFailed, act.result)
    message = result.response
    error = message.get("error", "")

    if act.did_timeout:
        return ActTimeoutError(metadata=act.metadata)
    if message.get("subErrorCode") == "AGENT_ERROR":
        return ActAgentError(message=error, metadata=act.metadata)
    if error == "Canceled.":
        return ActCanceledError(metadata=act.metadata)

    try:
        error_message = json.loads(error)
        request_id = error_message.get("requestId", "")
    except json.JSONDecodeError:
        return ActProtocolError(
            metadata=act.metadata,
            message="failed to load error message as json",
            raw_message=json.dumps(error),
        )

    if "type" not in error_message:
        return ActProtocolError(
            metadata=act.metadata,
            message="missing type in error message",
            failed_request_id=request_id,
            raw_message=json.dumps(error),
        )

    if error_message.get("type") == NOVA_ACT_SERVICE:
        return handle_nova_act_service_error(error_message, act, backend_info)
    if error_message.get("type") == NOVA_ACT_CLIENT:
        return handle_nova_act_client_error(error_message, act)

    return ActProtocolError(
        metadata=act.metadata,
        message="unhandled failure type",
        failed_request_id=request_id,
        raw_message=error,
    )


def handle_nova_act_service_error(error: dict, act: Act, backend_info: BackendInfo):
    request_id = error.get("requestId", "")
    code = error.get("code")

    if not isinstance(code, int) or code == -1:
        return ActProtocolError(
            metadata=act.metadata,
            message="invalid error code in Server Response",
            failed_request_id=request_id,
            raw_message=json.dumps(error),
        )

    message = error.get("message")

    if 400 == code:
        error_dict = check_error_is_json(message)
        if error_dict is None:
            return ActBadRequestError(
                metadata=act.metadata, failed_request_id=request_id, raw_message=json.dumps(error)
            )
        if "AGENT_GUARDRAILS_TRIGGERED" == error_dict.get("reason"):
            return ActGuardrailsError(message=error_dict, metadata=act.metadata)
        if "INVALID_INPUT" == error_dict.get("reason"):
            return ActInvalidInputError(metadata=act.metadata)
        if "MODEL_ERROR" == error_dict.get("reason"):
            return ActModelError(message=error_dict, metadata=act.metadata)
    if 403 == code:
        raise AuthError(backend_info, request_id=request_id)
        # else continue, fall back to generic 4xx
    if 429 == code:
        maybe_error_dict = check_error_is_json(message)
        return ActRateLimitExceededError(
            message=maybe_error_dict,
            metadata=act.metadata,
            failed_request_id=request_id,
            raw_message=json.dumps(error),
        )
    # 4xx
    if code < 500 and code >= 400:
        return ActBadRequestError(metadata=act.metadata, failed_request_id=request_id, raw_message=json.dumps(error))
    if 503 == code:
        return ActServiceUnavailableError(
            metadata=act.metadata, failed_request_id=request_id, raw_message=json.dumps(error)
        )
    # 5xx
    if code < 600 and code >= 500:
        return ActInternalServerError(
            metadata=act.metadata, failed_request_id=request_id, raw_message=json.dumps(error)
        )

    return ActProtocolError(
        message="Unhandled NovaActService error",
        metadata=act.metadata,
        failed_request_id=request_id,
        raw_message=json.dumps(error),
    )


def handle_nova_act_client_error(error: dict, act: Act):
    request_id = error.get("requestId")
    code = error.get("code", "")

    try:
        error_type = NovaActClientErrors[code]
    except (KeyError, TypeError, ValueError, IndexError) as e:
        return ActProtocolError(
            message="invalid NovaActClient error code",
            metadata=act.metadata,
            failed_request_id=request_id,
            raw_message=str(e),
        )

    if error_type == NovaActClientErrors.BAD_RESPONSE:
        return ActBadResponseError(metadata=act.metadata, failed_request_id=request_id, raw_message=json.dumps(error))
    if error_type == NovaActClientErrors.MAX_STEPS_EXCEEDED:
        return ActExceededMaxStepsError(metadata=act.metadata)

    return ActProtocolError(
        message="Unhandled NovaActClient error",
        metadata=act.metadata,
        failed_request_id=request_id,
        raw_message=json.dumps(error),
    )


def check_error_is_json(message: Any) -> dict | None:
    try:
        return json.loads(message)
    except (json.JSONDecodeError, TypeError):
        return None
