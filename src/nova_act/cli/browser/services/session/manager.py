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
"""Session management for interactive Nova Act CLI.

This module provides core session lifecycle management including state tracking,
session information storage, and session operations (create, get, list, close).
"""

import json
import logging
import os
import platform
import re
import subprocess
from contextlib import AbstractContextManager
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from nova_act.cli.browser.services.browser_config import DefaultBrowserConfig
from nova_act.cli.browser.services.session.chrome_launcher import ChromeLauncher
from nova_act.cli.browser.services.session.chrome_terminator import ChromeTerminator
from nova_act.cli.browser.services.session.closer import SessionCloser
from nova_act.cli.browser.services.session.connector import NovaActConnector
from nova_act.cli.browser.services.session.locking import SessionLockManager
from nova_act.cli.browser.services.session.models import (
    BrowserOptions,
    SessionInfo,
    SessionState,
)
from nova_act.cli.browser.services.session.persistence import SessionPersistence
from nova_act.cli.browser.services.session.pruner import PruneResult, SessionPruner
from nova_act.cli.core.config import get_browser_cli_dir, get_session_dir
from nova_act.cli.core.exceptions import (
    BrowserProcessDead,
    SessionLimitReached,
    SessionNotFoundError,
)
from nova_act.cli.core.process import is_process_running

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from nova_act.cli.browser.utils.auth import AuthConfig

# Active session states for filtering
ACTIVE_SESSION_STATES = frozenset({SessionState.STARTING, SessionState.STARTED})


def filter_active_sessions(sessions: list[SessionInfo]) -> list[SessionInfo]:
    """Filter sessions to only active states (STARTING, STARTED)."""
    return [s for s in sessions if s.state in ACTIVE_SESSION_STATES]


class SessionManager:
    """Manages Nova Act session lifecycle and state.

    Provides operations to create, retrieve, list, and close browser sessions.
    Sessions are stored in-memory and tracked by unique session IDs.
    Thread-safe session operations are supported via session locking.
    """

    def __init__(self, session_dir: str | None = None) -> None:
        """Initialize the session manager with empty session storage.

        Args:
            session_dir: Optional directory path for session storage.
                        Defaults to the standard session directory.

        Note: Sessions are NOT loaded from disk on initialization to avoid
        conflicts with active sessions. Use list_sessions() to discover
        persisted sessions.
        """
        self._session_dir = session_dir or str(get_session_dir())
        self._sessions: dict[str, SessionInfo] = {}
        self._lock_manager = SessionLockManager(Path(self._session_dir))
        self._chrome_launcher = ChromeLauncher(self._session_dir, self._get_used_ports)
        self._chrome_terminator = ChromeTerminator()
        self._persistence = SessionPersistence(self._session_dir)
        self._nova_act_connector = NovaActConnector(
            self._persistence,
            self._chrome_terminator,
        )
        self._session_closer = SessionCloser(
            self._lock_manager,
            self._chrome_terminator,
            self._persistence,
        )
        self._session_pruner = SessionPruner(
            self._persistence,
            self._chrome_terminator,
            self._lock_manager,
        )
        # No atexit handler and no nova_act.stop() on normal command exit.
        # CDP browsers persist across CLI invocations and are terminated only
        # via explicit close_session() calls.
        #
        # Design note: each CLI invocation creates a fresh Playwright instance
        # that connects to the persistent Chrome via CDP. When the process exits
        # without calling stop(), the OS closes the TCP socket and Chrome cleans
        # up the DevTools session automatically. Empirical testing (30 rapid-fire
        # subprocess iterations with navigation, JS eval, screenshots, and a11y
        # reads — all without stop()) showed 0 failures and stable target counts.
        # Calling stop() is therefore unnecessary for CDP cleanup and is
        # intentionally omitted to avoid risk of hangs on teardown.

    def _load_existing_sessions(self) -> None:
        """Load existing sessions from disk.

        Discovers session metadata files and reconstructs SessionInfo objects.
        Called from list_sessions() to merge persisted sessions with in-memory state.

        Note: Only loads sessions that don't already exist in memory to avoid
        overwriting active sessions with nova_act_instance=None.

        All loaded sessions are marked as STOPPED since the browser process
        is no longer running (sessions don't persist across process restarts).
        """
        loaded_sessions = self._persistence.load_existing_sessions(set(self._sessions.keys()))
        self._sessions.update(loaded_sessions)

    def _cleanup_stale_locks(self) -> None:
        """Remove lock files for sessions that no longer exist."""
        self._lock_manager.cleanup_stale_locks(set(self._sessions.keys()))

    def _get_used_ports(self) -> set[int]:
        """Get ports in use by both in-memory and persisted sessions."""
        in_memory_ports = {s.cdp_port for s in self._sessions.values() if s.cdp_port is not None}
        disk_ports = self._persistence.read_used_ports(set(self._sessions.keys()))
        return in_memory_ports | disk_ports

    def with_session_lock(self, session_id: str, timeout: float | None = None) -> AbstractContextManager[None]:
        """Context manager for file-based session locking.

        Args:
            session_id: Unique identifier for the session
            timeout: Maximum time to wait for lock acquisition in seconds
                    (default: SESSION_LOCK_TIMEOUT_SECONDS)

        Yields:
            None (lock is held during context)

        Raises:
            SessionNotFoundError: If session does not exist
            SessionLockTimeout: If lock cannot be acquired within timeout
        """

        def check_session_exists(sid: str) -> None:
            if sid not in self._sessions:
                raise SessionNotFoundError(f"Session '{sid}' not found")

        return self._lock_manager.with_lock(session_id, check_session_exists, timeout)

    _VALID_SESSION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+$")

    @staticmethod
    def _validate_session_id(session_id: str) -> None:
        """Validate session_id to prevent path traversal attacks.

        Args:
            session_id: The session ID to validate

        Raises:
            ValueError: If session_id is invalid
        """
        if not session_id or not session_id.strip():
            raise ValueError("Session ID must not be empty or whitespace-only")
        if "\x00" in session_id:
            raise ValueError("Session ID must not contain null bytes")
        if ".." in session_id or "/" in session_id or "\\" in session_id:
            raise ValueError("Session ID must not contain path separators or '..'")
        if not SessionManager._VALID_SESSION_ID_PATTERN.match(session_id):
            raise ValueError("Session ID must contain only alphanumeric characters, hyphens, underscores, or dots")

    def _initialize_session_info(self, session_id: str) -> SessionInfo:
        """Initialize session info and persist to disk.

        Args:
            session_id: Unique identifier for the session

        Returns:
            SessionInfo object in STARTING state
        """
        session_info = SessionInfo(
            session_id=session_id,
            state=SessionState.STARTING,
            nova_act_instance=None,
            created_at=datetime.now(),
            last_used=datetime.now(),
        )
        self._sessions[session_id] = session_info
        self._persistence.write_session_metadata(session_info)

        # Create lock file
        lock_path = self._lock_manager.get_lock_file_path(session_id)
        lock_path.touch()

        return session_info

    def _handle_browser_setup_failure(self, session_info: SessionInfo, error: Exception, context: str) -> None:
        """Handle browser setup failure by updating session state and persisting.

        Args:
            session_info: Session that failed
            error: Exception that caused the failure
            context: Context message describing what failed

        Raises:
            RuntimeError: Always raises with context and original error
        """
        session_info.state = SessionState.FAILED
        session_info.error_message = str(error)
        self._persistence.write_session_metadata(session_info)
        raise RuntimeError(f"{context}: {error}") from error

    def _launch_new_browser(
        self,
        session_info: SessionInfo,
        headless: bool,
        executable_path: str | None,
        profile_path: str | None,
        launch_args: list[str] | None = None,
    ) -> None:
        """Launch new Chrome browser instance.

        Args:
            session_info: Session to update with browser details
            headless: Whether to launch in headless mode
            executable_path: Optional custom browser executable
            profile_path: Optional browser profile path
            launch_args: Additional Chrome launch arguments

        Raises:
            RuntimeError: If launch fails
        """
        try:
            launch = self._chrome_launcher.launch_chrome_with_cdp(
                session_info.session_id, headless, executable_path, profile_path, launch_args
            )
            session_info.browser_pid = launch.process.pid
            session_info.cdp_endpoint = launch.ws_url
            session_info.cdp_port = launch.port
            session_info.user_data_dir = str(launch.user_data_dir)
        except RuntimeError as e:
            self._handle_browser_setup_failure(
                session_info,
                e,
                f"Failed to launch Chrome for session '{session_info.session_id}'",
            )

    @staticmethod
    def _is_system_chrome_data_dir(path: str) -> bool:
        """Check if a path is or is inside Chrome's default user data directory.

        Chrome blocks CDP when --user-data-dir points at its own default data
        directory. This detects that case so we can rsync to a managed copy first.

        Args:
            path: Resolved filesystem path to check

        Returns:
            True if path is Chrome's default data dir or a subdirectory of it
        """
        if platform.system() != "Darwin":
            return False
        default_chrome_dir = os.path.expanduser("~/Library/Application Support/Google/Chrome")
        try:
            resolved = str(Path(path).resolve())
            default_resolved = str(Path(default_chrome_dir).resolve())
            return os.path.samefile(resolved, default_resolved) or resolved.startswith(default_resolved + os.sep)
        except (OSError, ValueError):
            return False

    def _rsync_and_launch_chrome(
        self,
        session_info: SessionInfo,
        working_dir: str,
        *,
        headless: bool,
        executable_path: str | None,
        launch_args: list[str] | None = None,
    ) -> None:
        """Rsync default Chrome profile to working_dir, remove SingletonLock, and launch Chrome.

        Updates session_info with user_data_dir, browser_pid, cdp_endpoint, cdp_port.

        Args:
            session_info: Session to update with browser details
            working_dir: Directory to rsync Chrome data into and launch from
            headless: Whether to launch in headless mode
            executable_path: Optional custom browser executable
            launch_args: Additional Chrome launch arguments
        """
        try:
            from nova_act import rsync_from_default_user_data  # noqa: PLC0415

            rsync_from_default_user_data(working_dir)
        except (ImportError, subprocess.CalledProcessError, OSError) as e:
            self._handle_browser_setup_failure(
                session_info,
                e,
                f"Failed to rsync Chrome profile for session '{session_info.session_id}'",
            )

        session_info.user_data_dir = working_dir

        # Remove SingletonLock as safety net (rsync excludes Singleton* but belt-and-suspenders)
        (Path(working_dir) / "SingletonLock").unlink(missing_ok=True)

        try:
            launch = self._chrome_launcher.launch_chrome_with_user_data_dir(
                user_data_dir=Path(working_dir),
                headless=headless,
                executable_path=executable_path,
                launch_args=launch_args,
            )
            session_info.browser_pid = launch.process.pid
            session_info.cdp_endpoint = launch.ws_url
            session_info.cdp_port = launch.port
        except RuntimeError as e:
            self._handle_browser_setup_failure(
                session_info,
                e,
                f"Failed to launch Chrome for session '{session_info.session_id}'",
            )

    def _launch_with_rsynced_profile(self, session_info: SessionInfo, options: BrowserOptions) -> None:
        """Rsync system Chrome profile to a managed directory and launch Chrome.

        Used when --browser-profile-path points at Chrome's default data directory
        (or a subdirectory like Default/). Chrome blocks CDP on its own default
        data dir, so we rsync to a managed copy first — same approach as
        --use-default-chrome.

        Args:
            session_info: Session to configure with browser details
            options: Browser options with profile_path pointing at system Chrome

        Raises:
            RuntimeError: If rsync or launch fails
        """
        # Determine the profile subdirectory (e.g. "Default") if the user pointed
        # at a profile subdir rather than the top-level Chrome data dir.
        assert options.profile_path is not None, "profile_path required for system Chrome sync"
        profile_dir = Path(options.profile_path).expanduser().resolve()
        default_chrome_dir = Path(os.path.expanduser("~/Library/Application Support/Google/Chrome")).resolve()
        profile_directory: str | None = None
        if profile_dir != default_chrome_dir:
            # User pointed at a subdirectory like Default/ or "Profile 1/"
            profile_directory = str(profile_dir.relative_to(default_chrome_dir))

        # Create managed working directory
        working_dir_path = get_browser_cli_dir() / "chrome_profiles" / session_info.session_id
        working_dir_path.mkdir(parents=True, exist_ok=True)
        working_dir = str(working_dir_path)

        # Build launch args with profile directory if needed
        launch_args = list(options.launch_args) if options.launch_args else []
        if profile_directory:
            launch_args.append(f"--profile-directory={profile_directory}")

        self._rsync_and_launch_chrome(
            session_info,
            working_dir,
            headless=options.headless,
            executable_path=options.executable_path,
            launch_args=launch_args or None,
        )

    def _setup_browser(self, session_info: SessionInfo, options: BrowserOptions) -> None:
        """Setup browser by launching a new Chrome instance or preparing for default Chrome.

        Args:
            session_info: Session to configure with browser details
            options: Browser configuration options

        Raises:
            RuntimeError: If browser setup fails
        """
        if options.use_default_chrome:
            self._setup_default_chrome(session_info, options)
        elif options.profile_path and self._is_system_chrome_data_dir(
            str(Path(options.profile_path).expanduser().resolve())
        ):
            self._launch_with_rsynced_profile(session_info, options)
        else:
            self._launch_new_browser(
                session_info,
                options.headless,
                options.executable_path,
                options.profile_path,
                options.launch_args or None,
            )

    def _setup_default_chrome(self, session_info: SessionInfo, options: BrowserOptions) -> None:
        """Rsync Chrome profile and prepare session for NovaAct's default Chrome flow.

        Args:
            session_info: Session to configure
            options: Browser options with use_default_chrome=True

        Raises:
            RuntimeError: If not on macOS or rsync fails
        """
        if platform.system() != "Darwin":
            self._handle_browser_setup_failure(
                session_info,
                RuntimeError("--use-default-chrome is only supported on macOS"),
                "Platform check failed",
            )

        # Determine working directory
        if options.user_data_dir:
            working_dir = options.user_data_dir
        else:
            profile_dir = get_browser_cli_dir() / "chrome_profiles" / session_info.session_id
            profile_dir.mkdir(parents=True, exist_ok=True)
            working_dir = str(profile_dir)

        self._rsync_and_launch_chrome(
            session_info,
            working_dir,
            headless=options.headless,
            executable_path=options.executable_path,
            launch_args=options.launch_args or None,
        )

    def _count_active_sessions(self) -> int:
        """Count sessions in active states (STARTING or STARTED)."""
        self._load_existing_sessions()
        return sum(1 for s in self._sessions.values() if s.state in (SessionState.STARTING, SessionState.STARTED))

    def _cleanup_failed_session(self, session_id: str, session_info: SessionInfo) -> None:
        """Terminate browser, remove metadata file, remove lock, and delete from memory.

        Args:
            session_id: ID of the failed session
            session_info: Session info for the failed session
        """
        self._chrome_terminator.terminate(session_info.browser_pid)
        session_file = self._persistence.get_session_file_path(session_id)
        session_file.unlink(missing_ok=True)
        self._lock_manager.remove_lock(session_id)
        self._sessions.pop(session_id, None)

    def create_session(
        self,
        session_id: str,
        starting_page: str | None = None,
        browser_options: BrowserOptions | None = None,
        max_sessions: int | None = None,
    ) -> SessionInfo:
        """Create a new Nova Act session with CDP-based browser.

        Args:
            session_id: Unique identifier for the session
            starting_page: Optional URL to navigate to when starting the session
            browser_options: Browser configuration (headless, CDP endpoint, etc.)
            max_sessions: Maximum number of active sessions allowed
                (default: DefaultBrowserConfig.DEFAULT_MAX_ACTIVE_SESSIONS)

        Returns:
            SessionInfo object with session details

        Raises:
            ValueError: If session_id already exists
            SessionLimitReached: If max active sessions limit is reached
            RuntimeError: If Chrome launch or NovaAct.start() fails
        """
        self._validate_session_id(session_id)

        # Auto-prune stale sessions to prevent resource accumulation
        self.prune_sessions(ignore_ttl=False, dry_run=False)

        if session_id in self._sessions:
            existing = self._sessions[session_id]
            if existing.state == SessionState.FAILED:
                self._cleanup_failed_session(session_id, existing)
            else:
                raise ValueError(f"Session '{session_id}' already exists")

        limit = max_sessions if max_sessions is not None else DefaultBrowserConfig.DEFAULT_MAX_ACTIVE_SESSIONS
        active_count = self._count_active_sessions()
        if active_count >= limit:
            raise SessionLimitReached(
                f"Maximum active sessions ({limit}) reached. "
                f"Close existing sessions with 'act browser session close <id>' or "
                f"'act browser session close-all', or increase limit with --max-sessions."
            )

        options = browser_options or BrowserOptions()
        session_info = self._initialize_session_info(session_id)
        session_info.browser_options_meta = {
            "headless": options.headless,
            "headed": options.headed,
            "executable_path": options.executable_path,
            "profile_path": options.profile_path,
            "ignore_https_errors": options.ignore_https_errors,
            "launch_args": options.launch_args,
            "use_default_chrome": options.use_default_chrome,
            "user_data_dir": options.user_data_dir,
            "browser_source": "local",
        }
        if options.auth_config:
            session_info.auth_config = options.auth_config
        self._setup_browser(session_info, options)
        try:
            self._nova_act_connector.connect_to_session(
                session_info,
                starting_page,
                options.nova_args,
                auth_config=options.auth_config,
            )
            self._persistence.write_session_metadata(session_info)
        except BaseException:
            # Safety net: if connect_to_session raises anything not caught internally
            # (e.g. KeyboardInterrupt, SystemExit), ensure Chrome doesn't leak.
            if session_info.browser_pid and session_info.state != SessionState.FAILED:
                self._chrome_terminator.terminate(session_info.browser_pid)
                session_info.state = SessionState.FAILED
                self._persistence.write_session_metadata(session_info)
            raise
        return session_info

    def _validate_browser_running(self, session_info: SessionInfo) -> None:
        """Validate that browser process is still running.

        Args:
            session_info: Session to validate

        Raises:
            BrowserProcessDead: If browser process is dead
        """
        if session_info.browser_pid and not is_process_running(session_info.browser_pid):
            raise BrowserProcessDead(
                f"Browser process {session_info.browser_pid} is no longer running. "
                f"Close this session and create a new one: "
                f"act browser session close {session_info.session_id} && "
                f"act browser session create <url> --session-id {session_info.session_id}"
            )

    def get_session(self, session_id: str, auth_config: "AuthConfig | None" = None) -> SessionInfo:
        """Retrieve an existing session by ID, reconnecting if needed.

        Args:
            session_id: Unique identifier for the session
            auth_config: Authentication configuration for reconnection (overrides stored config)

        Returns:
            SessionInfo object for the session

        Raises:
            SessionNotFoundError: If session_id does not exist
            BrowserProcessDead: If browser process is dead
            RuntimeError: If reconnection fails
        """
        if session_id not in self._sessions:
            try:
                session_info = self._persistence.load_session(session_id)
                self._sessions[session_id] = session_info
            except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError) as e:
                raise SessionNotFoundError(f"Session '{session_id}' not found") from e

        session_info = self._sessions[session_id]

        if session_info.cdp_endpoint and not session_info.nova_act_instance:
            self._validate_browser_running(session_info)
            effective_auth = auth_config or session_info.auth_config
            self._nova_act_connector.reconnect_to_session(session_info, auth_config=effective_auth)
            self._persistence.write_session_metadata(session_info)

        return session_info

    def session_exists(self, session_id: str) -> bool:
        """Check if a session exists without reconnecting or modifying state."""
        if session_id in self._sessions:
            return True
        return self._persistence.get_session_file_path(session_id).exists()

    def save_session_metadata(self, session_info: SessionInfo) -> None:
        """Persist current session metadata to disk.

        Args:
            session_info: Session to persist.
        """
        self._persistence.write_session_metadata(session_info)

    def _warn_orphaned_sessions(self, sessions: list[SessionInfo]) -> None:
        """Log warnings for orphaned sessions (browser process no longer running)."""
        orphaned_sessions = [s for s in sessions if s.is_orphaned]
        if not orphaned_sessions:
            return
        orphan_details = [f"  • Session '{s.session_id}' (PID: {s.browser_pid})" for s in orphaned_sessions]
        cleanup_lines = [f"  act browser session close --force {s.session_id}" for s in orphaned_sessions]
        logger.warning(
            "Orphaned browser sessions detected!\n"
            "These sessions have browser processes that are no longer running:\n\n%s\n\n"
            "To clean up, run:\n%s",
            "\n".join(orphan_details),
            "\n".join(cleanup_lines),
        )

    def list_sessions(self) -> list[SessionInfo]:
        """List all sessions (active and inactive).

        Loads persisted sessions from disk and checks for orphaned sessions.

        Returns:
            List of SessionInfo objects for all sessions
        """
        self._load_existing_sessions()
        self._cleanup_stale_locks()

        sessions = list(self._sessions.values())
        self._warn_orphaned_sessions(sessions)
        return sessions

    def close_session(self, session_id: str, force: bool = False) -> None:
        """Close an existing Nova Act session and terminate Chrome browser.

        Args:
            session_id: Unique identifier for the session
            force: If True, skip NovaAct.stop() and remove session files immediately

        Raises:
            SessionNotFoundError: If session_id does not exist
            RuntimeError: If NovaAct.stop() fails (only when force=False)
        """
        session_info = self._session_closer.load_session_for_close(session_id, force, self._sessions, self.get_session)

        if force:
            self._session_closer.force_close(session_id, session_info, self._sessions)
            return

        if session_info.state == SessionState.FAILED:
            self._session_closer.cleanup_failed_session(session_id)
            return

        self._session_closer.normal_close(session_id, session_info, self._sessions)

    def prune_sessions(self, ignore_ttl: bool = False, dry_run: bool = False) -> list[PruneResult]:
        """Remove stale or inactive sessions and their Chrome profile directories.

        Args:
            ignore_ttl: If True, prune all non-active sessions regardless of TTL
            dry_run: If True, return what would be pruned without deleting

        Returns:
            List of PruneResult for each pruned session.
        """
        self._load_existing_sessions()
        return self._session_pruner.prune(
            self._sessions,
            ignore_ttl=ignore_ttl,
            dry_run=dry_run,
        )
