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
"""Session pruning logic extracted from SessionManager."""

import shutil
from dataclasses import dataclass
from pathlib import Path

import psutil

from nova_act.cli.browser.services.session.chrome_terminator import ChromeTerminator
from nova_act.cli.browser.services.session.locking import SessionLockManager
from nova_act.cli.browser.services.session.models import SessionInfo, SessionState
from nova_act.cli.browser.services.session.persistence import SessionPersistence
from nova_act.cli.browser.utils.log_capture import cleanup_session_logs
from nova_act.cli.core.config import get_cli_config_dir

_CLI_CONFIG_DIR = get_cli_config_dir()


def _has_dead_pid(session: SessionInfo) -> bool:
    """Check if a non-active session's browser PID is dead.

    Returns True if the session has a browser PID that is no longer running,
    indicating the session is safe to prune regardless of TTL.
    """
    if session.browser_pid is None:
        return True  # No PID means browser is gone — safe to prune
    try:
        process = psutil.Process(session.browser_pid)
        return not process.is_running()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return True


@dataclass(frozen=True)
class PruneResult:
    """Result of pruning a single session.

    Attributes:
        session_id: ID of the pruned session.
        user_data_dir: Path to the Chrome user data directory (if any).
    """

    session_id: str
    user_data_dir: str | None = None


def _should_delete_user_data_dir(session_info: SessionInfo) -> bool:
    """Determine if a session's user_data_dir is safe to delete.

    Returns True only when:
    - The session has a user_data_dir
    - It is NOT the user's explicitly provided profile path
    - It resides within the CLI config directory
    """
    if not session_info.user_data_dir:
        return False
    raw_profile = session_info.browser_options_meta.get("profile_path") if session_info.browser_options_meta else None
    if (
        raw_profile
        and isinstance(raw_profile, str)
        and str(Path(raw_profile).resolve()) == str(Path(session_info.user_data_dir).resolve())
    ):
        return False
    try:
        Path(session_info.user_data_dir).resolve().relative_to(_CLI_CONFIG_DIR.resolve())
    except ValueError:
        return False
    return True


class SessionPruner:
    """Prunes stale or inactive sessions and their Chrome profile directories."""

    def __init__(
        self,
        persistence: SessionPersistence,
        chrome_terminator: ChromeTerminator,
        lock_manager: SessionLockManager,
    ) -> None:
        self._persistence = persistence
        self._chrome_terminator = chrome_terminator
        self._lock_manager = lock_manager

    def prune(
        self,
        sessions: dict[str, SessionInfo],
        ignore_ttl: bool = False,
        dry_run: bool = False,
    ) -> list[PruneResult]:
        """Remove stale or inactive sessions and their Chrome profile directories.

        Args:
            sessions: In-memory session dictionary (mutated: pruned entries removed)
            ignore_ttl: If True, prune all non-active sessions regardless of TTL
            dry_run: If True, return what would be pruned without deleting

        Returns:
            List of PruneResult for each pruned session.
        """
        active_states = (SessionState.STARTING, SessionState.STARTED)
        pruneable = [
            s
            for s in sessions.values()
            if s.state not in active_states and (ignore_ttl or s.is_stale or _has_dead_pid(s))
        ]

        results: list[PruneResult] = []
        for session_info in pruneable:
            results.append(PruneResult(session_id=session_info.session_id, user_data_dir=session_info.user_data_dir))
            if dry_run:
                continue
            self._chrome_terminator.terminate(session_info.browser_pid)
            if _should_delete_user_data_dir(session_info):
                assert session_info.user_data_dir is not None  # guaranteed by _should_delete_user_data_dir
                shutil.rmtree(session_info.user_data_dir, ignore_errors=True)
            session_file = self._persistence.get_session_file_path(session_info.session_id)
            session_file.unlink(missing_ok=True)
            cleanup_session_logs(session_info.session_id)
            sessions.pop(session_info.session_id, None)
            self._lock_manager.remove_lock(session_info.session_id)

        return results
