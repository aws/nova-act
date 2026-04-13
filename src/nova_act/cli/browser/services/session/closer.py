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
"""Session closing logic for interactive Nova Act CLI.

Handles the various close scenarios: normal close, force close, and failed session cleanup.
"""

from __future__ import annotations

import json
import logging
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import click

from nova_act.cli.browser.services.session.chrome_terminator import ChromeTerminator
from nova_act.cli.browser.services.session.locking import SessionLockManager
from nova_act.cli.browser.services.session.models import (
    SessionInfo,
    SessionState,
)
from nova_act.cli.browser.services.session.persistence import SessionPersistence
from nova_act.cli.browser.utils.log_capture import suppress_sdk_output
from nova_act.cli.core.config import get_cli_config_dir
from nova_act.cli.core.exceptions import SessionNotFoundError
from nova_act.cli.core.output import is_verbose_mode

if TYPE_CHECKING:
    from nova_act.cli.browser.services.session.manager import SessionManager

logger = logging.getLogger(__name__)

_CLI_CONFIG_DIR = get_cli_config_dir()


class SessionCloser:
    """Handles session closing operations.

    Separates close logic from SessionManager to reduce complexity and improve testability.
    """

    def __init__(
        self,
        lock_manager: SessionLockManager,
        chrome_terminator: ChromeTerminator,
        persistence: SessionPersistence,
    ):
        """Initialize SessionCloser with required dependencies.

        Args:
            lock_manager: Manages session locks
            chrome_terminator: Handles Chrome process termination
            persistence: Handles session metadata persistence
        """
        self._lock_manager = lock_manager
        self._chrome_terminator = chrome_terminator
        self._persistence = persistence

    def load_session_for_close(
        self, session_id: str, force: bool, sessions: dict[str, SessionInfo], get_session: Callable[[str], SessionInfo]
    ) -> SessionInfo:
        """Load session info for closing, bypassing validation if force=True."""
        if force:
            if session_id in sessions:
                return sessions[session_id]

            try:
                return self._persistence.load_session(session_id)
            except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError) as e:
                raise SessionNotFoundError(f"Session '{session_id}' not found") from e

        return get_session(session_id)

    def _cleanup_lock(self, session_id: str) -> None:
        """Clean up session lock from memory and filesystem.

        Args:
            session_id: ID of session to clean up lock for
        """
        self._lock_manager.remove_lock(session_id)

    def _cleanup_session_files(self, session_id: str, sessions: dict[str, SessionInfo]) -> None:
        """Remove session metadata file and in-memory reference.

        Args:
            session_id: ID of session to clean up
            sessions: In-memory session dictionary
        """
        file_path = self._persistence.get_session_file_path(session_id)
        if file_path.exists():
            file_path.unlink()

        if session_id in sessions:
            del sessions[session_id]

    def _cleanup_user_data_dir(self, session_info: SessionInfo) -> None:
        """Remove Chrome user data directory if it's a managed directory.

        Only deletes directories under the CLI config dir (managed by us).
        User-provided --profile-path directories are NOT deleted.

        Args:
            session_info: Session whose user_data_dir to clean up
        """
        user_data_dir = session_info.user_data_dir
        if not user_data_dir:
            return
        profile_path = None
        browser_opts = session_info.browser_options_meta
        if isinstance(browser_opts, dict):
            raw_profile = browser_opts.get("profile_path")
            profile_path = str(raw_profile) if raw_profile else None
        if profile_path and str(Path(profile_path).resolve()) == str(Path(user_data_dir).resolve()):
            return
        # Safety guard: only delete directories under CLI config dir to prevent
        # accidental deletion of user Chrome data directories
        try:
            Path(user_data_dir).resolve().relative_to(_CLI_CONFIG_DIR.resolve())
        except ValueError:
            return
        shutil.rmtree(user_data_dir, ignore_errors=True)

    def _terminate_browser(self, session_info: SessionInfo) -> None:
        """Terminate local Chrome browser process."""
        self._chrome_terminator.terminate(session_info.browser_pid)

    def force_close(self, session_id: str, session_info: SessionInfo, sessions: dict[str, SessionInfo]) -> None:
        """Force close session: attempt lock, warn if busy, then terminate."""
        lock_acquired = self._lock_manager.try_acquire(session_id)
        if not lock_acquired:
            click.echo(f"Warning: Session '{session_id}' may be in use by another process. " "Force closing anyway.")
        try:
            self._terminate_browser(session_info)
        finally:
            if lock_acquired:
                self._lock_manager.release(session_id)
            self._cleanup_lock(session_id)
            self._cleanup_user_data_dir(session_info)
            self._cleanup_session_files(session_id, sessions)

    def cleanup_failed_session(self, session_id: str) -> None:
        """Clean up lock for failed session, preserving metadata for debugging."""
        self._cleanup_lock(session_id)

    def normal_close(self, session_id: str, session_info: SessionInfo, sessions: dict[str, SessionInfo]) -> None:
        """Normal close: stop NovaAct, terminate browser (local or cloud), and clean up."""
        session_info.state = SessionState.STOPPING
        error: Exception | None = None

        try:
            if session_info.nova_act_instance:
                if is_verbose_mode():
                    session_info.nova_act_instance.stop()
                else:
                    with suppress_sdk_output():
                        session_info.nova_act_instance.stop()

            self._terminate_browser(session_info)
            session_info.state = SessionState.STOPPED
        except RuntimeError as e:
            error = e
            session_info.state = SessionState.FAILED
            session_info.error_message = str(e)
        finally:
            self._persistence.write_session_metadata(session_info)

            try:
                self._cleanup_lock(session_id)
            except OSError:
                logger.debug("Failed to clean up lock for session '%s'", session_id, exc_info=True)

            if session_info.state == SessionState.STOPPED:
                self._cleanup_user_data_dir(session_info)
                self._cleanup_session_files(session_id, sessions)

        if error is not None:
            raise RuntimeError(f"Failed to stop session '{session_id}': {error}") from error

    @staticmethod
    def close_sessions_batch(
        manager: SessionManager, sessions: list[SessionInfo], force: bool
    ) -> tuple[list[str], list[str]]:
        """Close multiple sessions and track results.

        Args:
            manager: SessionManager instance to close sessions through
            sessions: List of sessions to close
            force: Whether to force close

        Returns:
            Tuple of (closed_session_ids, failed_session_descriptions)
        """
        closed_ids: list[str] = []
        failed_sessions: list[str] = []

        for session in sessions:
            try:
                manager.close_session(session.session_id, force=force)
                closed_ids.append(session.session_id)
            except (
                Exception
            ) as e:  # noqa: BLE001 — batch operation error boundary; must continue closing remaining sessions
                failed_sessions.append(f"{session.session_id}: {e}")

        return closed_ids, failed_sessions
