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
"""Session data models for Nova Act CLI.

This module defines the core data structures for session management.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING

import psutil

from nova_act.cli.browser.services.browser_config import DefaultBrowserConfig
from nova_act.cli.browser.utils.auth import AuthConfig

if TYPE_CHECKING:
    from nova_act import NovaAct


class BrowserSource(Enum):
    """Source of the browser instance.

    Attributes:
        LOCAL: Browser launched locally via ChromeLauncher
    """

    LOCAL = "local"


class SessionState(Enum):
    """Lifecycle states for a managed session.

    Attributes:
        STARTING: Session is being initialized
        STARTED: Session is active and ready for commands
        STOPPING: Session is being terminated
        STOPPED: Session has been cleanly terminated
        FAILED: Session encountered an error during start or operation
    """

    STARTING = "starting"
    STARTED = "started"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class BrowserOptions:
    """Browser configuration options for session creation.

    Attributes:
        headless: Launch browser in headless mode (no visible UI)
        headed: Launch browser in headed mode (visible UI) - overrides headless
        executable_path: Path to custom Chromium-based browser executable
        profile_path: Path to browser profile directory for persistent sessions
        nova_args: Additional arguments to pass to NovaAct constructor
    """

    headless: bool = True
    headed: bool = False
    executable_path: str | None = None
    profile_path: str | None = None
    ignore_https_errors: bool = True
    nova_args: dict[str, object] = field(default_factory=dict)
    launch_args: list[str] = field(default_factory=list)
    auth_config: AuthConfig | None = None
    use_default_chrome: bool = False
    user_data_dir: str | None = None
    cdp_endpoint_url: str | None = None


@dataclass
class SessionInfo:
    """Information about a Nova Act session.

    Attributes:
        session_id: Unique identifier for the session
        state: Current lifecycle state of the session
        nova_act_instance: The NovaAct client instance (None if not started)
        created_at: Timestamp when session was created
        browser_pid: Process ID of the browser (None if not started)
        user_data_dir: Path to browser user data directory (None if not started)
        last_used: Timestamp when session was last used
        cdp_endpoint: Chrome DevTools Protocol WebSocket URL (None if not using CDP)
        cdp_port: Port number for CDP connection (None if not using CDP)
        error_message: Error message if session failed
        browser_options_meta: Serialized browser options for persistence
        auth_config: Authentication configuration used for this session
    """

    session_id: str
    state: SessionState
    nova_act_instance: NovaAct | None
    created_at: datetime
    browser_pid: int | None = None
    user_data_dir: str | None = None
    last_used: datetime | None = None
    cdp_endpoint: str | None = None
    cdp_port: int | None = None
    error_message: str | None = None
    browser_options_meta: dict[str, object] = field(default_factory=dict)
    auth_config: AuthConfig | None = None
    active_tab_index: int = 0

    @property
    def is_orphaned(self) -> bool:
        """Check if session is orphaned (browser process died but session marked as STARTED).

        Returns:
            True if session is orphaned, False otherwise
        """
        if self.state != SessionState.STARTED:
            return False

        if self.browser_pid is None:
            return False

        try:
            process = psutil.Process(self.browser_pid)
            return not process.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return True

    def to_dict(self) -> dict[str, object]:
        """Serialize session info to a dictionary suitable for JSON persistence.

        Returns:
            Dictionary with all serializable session fields.
            Excludes nova_act_instance. Formats datetimes as ISO strings
            and state as its string value.
        """
        metadata: dict[str, object] = {}
        if self.error_message:
            metadata["error_message"] = self.error_message
        if self.browser_options_meta:
            metadata["browser_options"] = self.browser_options_meta
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "browser_pid": self.browser_pid,
            "user_data_dir": self.user_data_dir,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "cdp_endpoint": self.cdp_endpoint,
            "cdp_port": self.cdp_port,
            "browser_source": BrowserSource.LOCAL.value,
            "active_tab_index": self.active_tab_index,
            "metadata": metadata,
        }

    @property
    def is_stale(self) -> bool:
        """Check if session is stale (no activity within TTL period).

        A session is stale if its last activity timestamp is older than
        SESSION_STALE_TTL_HOURS. Uses last_used if available, otherwise created_at.

        Returns:
            True if session is stale, False otherwise
        """
        reference_time = self.last_used or self.created_at
        return datetime.now() - reference_time > timedelta(hours=DefaultBrowserConfig.SESSION_STALE_TTL_HOURS)
