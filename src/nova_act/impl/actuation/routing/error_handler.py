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
from typing import cast

from nova_act.impl.backend import BackendInfo
from nova_act.impl.protocol import (
    NOVA_ACT_CLIENT,
    NOVA_ACT_SERVICE,
    handle_nova_act_client_error,
    handle_nova_act_service_error,
)
from nova_act.types.act_errors import (
    ActAgentError,
    ActCanceledError,
    ActClientError,
    ActError,
    ActProtocolError,
    ActTimeoutError,
)
from nova_act.types.act_result import ActResult
from nova_act.types.state.act import Act, ActCanceled, ActFailed, ActSucceeded


def handle_error(act: Act, backend_info: BackendInfo) -> ActResult | ActError:
    """
    Handle errors from the actuator.
    Raises errors, otherwise returns successful act result.
    """
    if act.result is None:
        return ActClientError(message="No act result received", metadata=act.metadata)
    if isinstance(act.result, ActCanceled):
        return ActCanceledError(metadata=act.metadata)

    elif isinstance(act.result, ActFailed):
        return parse_act_failed(act, backend_info)

    elif isinstance(act.result, ActSucceeded):
        return ActResult(
            response=act.result.response,
            metadata=act.metadata,
        )

    else:
        return ActClientError(message="Unhandled act result", metadata=act.metadata)


def parse_act_failed(act: Act, backend_info: BackendInfo) -> ActResult | ActError:
    result = cast(ActFailed, act.result)
    message = result.response
    error = message.get("error", "")

    if act.did_timeout:
        return ActTimeoutError(metadata=act.metadata)
    if message.get("subErrorCode") == "AGENT_ERROR":
        return ActAgentError(message=error, metadata=act.metadata)
    if error == "Canceled.":
        return ActCanceledError(metadata=act.metadata)

    request_id = message.get("requestId", "")

    if "type" not in message:
        return ActProtocolError(
            metadata=act.metadata,
            message="missing type in error message" + json.dumps(error),
            failed_request_id=request_id,
        )

    if message.get("type") == NOVA_ACT_SERVICE:
        return handle_nova_act_service_error(message, act, backend_info)
    if message.get("type") == NOVA_ACT_CLIENT:
        return handle_nova_act_client_error(message, act)

    return ActProtocolError(
        metadata=act.metadata,
        message="unhandled failure type" + error,
        failed_request_id=request_id,
    )
