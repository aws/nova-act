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
"""Browser services module."""

from nova_act.cli.browser.services.session.chrome_launcher import ChromeLauncher
from nova_act.cli.browser.services.session.chrome_terminator import ChromeTerminator
from nova_act.cli.browser.services.session.locking import SessionLockManager
from nova_act.cli.browser.services.session.manager import SessionManager
from nova_act.cli.browser.services.session.models import (
    BrowserOptions,
    SessionInfo,
    SessionState,
)
from nova_act.cli.browser.services.session.persistence import SessionPersistence
from nova_act.cli.core.exceptions import SessionLockTimeout

__all__ = [
    "BrowserOptions",
    "SessionInfo",
    "SessionState",
    "SessionLockTimeout",
    "SessionLockManager",
    "ChromeLauncher",
    "ChromeTerminator",
    "SessionPersistence",
    "SessionManager",
]
