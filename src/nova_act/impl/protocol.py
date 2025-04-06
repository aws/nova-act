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
from typing import cast

from nova_act.impl.backend import BackendInfo
from nova_act.types.act_errors import (
    ActAgentError,
    ActCanceledError,
    ActClientError,
    ActExceededMaxStepsError,
    ActGuardrailsError,
    ActInternalServerError,
    ActProtocolError,
    ActRateLimitExceededError,
    ActServiceUnavailableError,
    ActTimeoutError,
)
from nova_act.types.errors import AuthError
from nova_act.types.state.act import Act, ActFailed

NOVA_ACT_SERVICE_PREFIX = "NovaActService"
NOVA_ACT_CLIENT_PREFIX = "NovaActClient"


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

    if error.startswith(NOVA_ACT_SERVICE_PREFIX):
        return handle_nova_act_service_error(error, act, backend_info)
    elif error.startswith(NOVA_ACT_CLIENT_PREFIX):
        return handle_nova_act_client_error(error, act)
    elif message.get("subErrorCode") == "AGENT_ERROR":
        return ActAgentError(message=error, metadata=act.metadata)
    elif error == "Canceled.":
        return ActCanceledError(metadata=act.metadata)

    out = "unhandled failure type"
    return ActProtocolError(metadata=act.metadata, message=out)


QUOTA_MESSAGE = (
    "We have quota limits to ensure sufficient capacity for all users. If you need dedicated "
    "quota for a more ambitious project, please get in touch at nova-act@amazon.com. "
    "We're excited to see what you build!"
)


def handle_nova_act_service_error(error_string: str, act: Act, backend_info: BackendInfo):
    message = NOVA_ACT_SERVICE_PREFIX

    try:
        prefix_part, json_part = error_string.split(" - ", 1)
        code = int(prefix_part.split(": ")[1])
        error_dict = json.loads(json_part)
    except (json.JSONDecodeError, ValueError, IndexError):
        return ActProtocolError(metadata=act.metadata, message=message)

    if 403 == code:
        raise AuthError(backend_info)
    if 400 == code:
        if "AGENT_GUARDRAILS_TRIGGERED" == error_dict.get("reason"):
            fields = error_dict.get("fields")
            if fields is not None and len(fields) > 0:
                return ActGuardrailsError(message=fields[0].get("message"), metadata=act.metadata)
            else:
                return ActGuardrailsError(metadata=act.metadata)
    if 429 == code:
        if "DAILY_QUOTA_LIMIT_EXCEEDED" == error_dict.get("throttleType"):
            return ActRateLimitExceededError(
                message="Daily API limit exceeded. " + QUOTA_MESSAGE,
                metadata=act.metadata,
            )
        if "RATE_LIMIT_EXCEEDED" == error_dict.get("throttleType"):
            return ActRateLimitExceededError(
                message="Too many requests in a short time period. " + QUOTA_MESSAGE,
                metadata=act.metadata,
            )
        return ActRateLimitExceededError(message=message, metadata=act.metadata)
    if 503 == code:
        return ActServiceUnavailableError(message=message, metadata=act.metadata)
    # 4xx
    if code < 500 and code >= 400:
        return ActClientError(message=message, metadata=act.metadata)
    # 5xx
    if code < 600 and code >= 500:
        return ActInternalServerError(message=message, metadata=act.metadata)
    return ActProtocolError(message=message, metadata=act.metadata)


def handle_nova_act_client_error(error_string: str, act: Act):
    message = NOVA_ACT_CLIENT_PREFIX

    try:
        prefix_part, message_part = error_string.split(" - ", 1)
        enum = prefix_part.split(": ")[1]
        error_type = NovaActClientErrors[enum]
    except (KeyError, TypeError, ValueError, IndexError):
        return ActProtocolError(message=message, metadata=act.metadata)

    if error_type == NovaActClientErrors.BAD_RESPONSE:
        return ActProtocolError(message=message, metadata=act.metadata)
    if error_type == NovaActClientErrors.MAX_STEPS_EXCEEDED:
        return ActExceededMaxStepsError(metadata=act.metadata)
    return ActProtocolError(message=message, metadata=act.metadata)
