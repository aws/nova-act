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
import platform
import sys
from typing import Literal

import requests

from nova_act.__version__ import VERSION
from nova_act.types.act_result import ActResult
from nova_act.types.errors import NovaActError
from nova_act.types.state.act import Act
from nova_act.util.logging import setup_logging

_LOGGER = setup_logging(__name__)


def send_act_telemetry(
    endpoint: str, nova_act_api_key: str | None, act: Act, success: ActResult | None, error: NovaActError | None
) -> None:
    """Send telemetry for the given act."""
    if not nova_act_api_key:
        return

    headers = {
        "Authorization": f"ApiKey {nova_act_api_key}",
        "Content-Type": "application/json",
        "X-Api-Key": f"{nova_act_api_key}",
    }

    latency = -1.0
    if act.end_time is not None:
        latency = act.end_time - act.start_time

    if error:
        result = {
            "result_type": "ERROR",
            "result_error": {
                "type": error.__class__.__name__,
                "message": error.message if hasattr(error, "message") and error.message else "",
            },
        }
    elif success:
        result = {
            "result_type": "SUCCESS",
            "result_success": {"response": success.response if success.response else ""},
        }
    else:
        return

    payload = {
        "act": {
            "actId": act.id,
            "latency": latency,
            "sessionId": act.session_id,
            **result,
        },
        "type": "ACT",
    }

    try:
        response = requests.post(endpoint + "/telemetry", json=payload, headers=headers)
        if response.status_code != 200:
            _LOGGER.debug("Failed to send act telemetry: %s", response.text)
    except Exception as e:
        # Swallow any exceptions
        _LOGGER.debug("Error sending act telemetry: %s", e)


def send_environment_telemetry(
    endpoint: str,
    nova_act_api_key: str | None,
    session_id: str,
    actuator_type: Literal["custom", "playwright"],
) -> None:
    """Send environment telemetry"""
    if not nova_act_api_key:
        return

    headers = {
        "Authorization": f"ApiKey {nova_act_api_key}",
        "Content-Type": "application/json",
        "X-Api-Key": f"{nova_act_api_key}",
    }

    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    system_name = platform.system().lower() or "unknown"
    system_release = platform.release().lower() or "unknown"
    system = f"{system_name}/{system_release}"

    payload = {
        "environment": {
            "actuatorType": actuator_type,
            "pythonVersion": python_version,
            "sessionId": session_id,
            "sdkVersion": VERSION,
            "system": system,
        },
        "type": "ENVIRONMENT",
    }

    try:
        response = requests.post(endpoint + "/telemetry", json=payload, headers=headers)
        if response.status_code != 200:
            _LOGGER.debug("Failed to send environment telemetry: %s", response.text)
    except Exception as e:
        # Swallow any exceptions
        _LOGGER.debug("Error sending environment telemetry: %s", e)
