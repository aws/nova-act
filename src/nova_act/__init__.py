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
import builtins
import pdb
import sys
import threading

from nova_act.impl.actuation.interface.browser import BrowserActuatorBase, JSONSerializable
from nova_act.impl.actuation.interface.playwright_pages import PlaywrightPageManagerBase
from nova_act.impl.actuation.playwright.default_nova_local_browser_actuator import (
    DefaultNovaLocalBrowserActuator,
)
from nova_act.impl.common import rsync_from_default_user_data
from nova_act.impl.extension import ExtensionActuator
from nova_act.nova_act import NovaAct
from nova_act.types.act_errors import (
    ActActuationError,
    ActAgentError,
    ActCanceledError,
    ActClientError,
    ActDispatchError,
    ActError,
    ActExceededMaxStepsError,
    ActGuardrailsError,
    ActInternalServerError,
    ActModelError,
    ActNotAuthorizedError,
    ActProtocolError,
    ActRateLimitExceededError,
    ActServerError,
    ActTimeoutError,
)
from nova_act.types.act_metadata import ActMetadata
from nova_act.types.act_result import ActResult
from nova_act.types.errors import NovaActError, StartFailed, StopFailed, ValidationFailed
from nova_act.util.jsonschema import BOOL_SCHEMA
from nova_act.util.logging import setup_logging

__all__ = [
    "NovaAct",
    "ActAgentError",
    "ActActuationError",
    "ActCanceledError",
    "ActClientError",
    "ActDispatchError",
    "ActError",
    "ActExceededMaxStepsError",
    "ActGuardrailsError",
    "ActInternalServerError",
    "ActNotAuthorizedError",
    "ActModelError",
    "ActRateLimitExceededError",
    "ActTimeoutError",
    "ActMetadata",
    "ActResult",
    "NovaActError",
    "StartFailed",
    "StopFailed",
    "ValidationFailed",
    "BOOL_SCHEMA",
    "BrowserActuatorBase",
    "ExtensionActuator",
    "DefaultNovaLocalBrowserActuator",
    "JSONSerializable",
    "rsync_from_default_user_data"
]


# Intercept `builtins.breakpoint` to disable KeyboardEventWatcher
from nova_act.impl.keyboard_event_watcher import DEBUGGER_ATTACHED_EVENT

_LOGGER = setup_logging(__name__)


def set_trace_and_signal_event(*args, **kwargs):  # type: ignore[no-untyped-def]
    _LOGGER.info("Intercepted breakpoint call. Signaling threads.")
    DEBUGGER_ATTACHED_EVENT.set()
    pdb.Pdb().set_trace(sys._getframe(1))


builtins.breakpoint = set_trace_and_signal_event
