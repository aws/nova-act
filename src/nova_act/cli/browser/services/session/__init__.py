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
"""Session management services."""

from nova_act.cli.browser.services.session.cdp_endpoint_manager import (
    CdpEndpointManager,
)
from nova_act.cli.browser.services.session.chrome_launcher import ChromeLauncher
from nova_act.cli.browser.services.session.chrome_terminator import ChromeTerminator
from nova_act.cli.browser.services.session.closer import SessionCloser
from nova_act.cli.browser.services.session.connector import NovaActConnector
from nova_act.cli.browser.services.session.locking import SessionLockManager
from nova_act.cli.browser.services.session.manager import (
    ACTIVE_SESSION_STATES,
    SessionManager,
    filter_active_sessions,
)
from nova_act.cli.browser.services.session.models import (
    BrowserOptions,
    BrowserSource,
    SessionInfo,
    SessionState,
)
from nova_act.cli.browser.services.session.persistence import SessionPersistence
from nova_act.cli.core.exceptions import SessionLockTimeout, SessionNotFoundError

__all__ = [
    "ACTIVE_SESSION_STATES",
    "BrowserOptions",
    "BrowserSource",
    "CdpEndpointManager",
    "ChromeLauncher",
    "ChromeTerminator",
    "NovaActConnector",
    "SessionCloser",
    "SessionInfo",
    "SessionLockManager",
    "SessionLockTimeout",
    "SessionManager",
    "SessionNotFoundError",
    "SessionPersistence",
    "SessionState",
    "filter_active_sessions",
]
