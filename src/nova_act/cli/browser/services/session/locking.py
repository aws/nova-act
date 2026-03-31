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
"""Session locking utilities for Nova Act CLI.

Thin wrapper around core/locking.py's FileLockManager for session-specific locking.
"""

import logging
from pathlib import Path

from filelock import Timeout as FileLockTimeout

from nova_act.cli.browser.services.browser_config import DefaultBrowserConfig
from nova_act.cli.core.locking import FileLockManager

logger = logging.getLogger(__name__)


class SessionLockManager(FileLockManager):
    """Manages file-based locks for session operations.

    Extends FileLockManager with browser-specific default timeout.
    """

    def __init__(self, session_dir: Path):
        """Initialize the session lock manager.

        Args:
            session_dir: Directory where session files are stored
        """
        super().__init__(session_dir, default_timeout=DefaultBrowserConfig.SESSION_LOCK_TIMEOUT_SECONDS)

    def cleanup_stale_locks(self, known_session_ids: set[str]) -> None:
        """Remove lock files for sessions that no longer exist on disk or in memory.

        Args:
            known_session_ids: Set of session IDs currently tracked in memory.
        """
        for lock_file in self.lock_dir.glob("*.lock"):
            session_id = lock_file.stem
            session_file = self.lock_dir / f"{session_id}.json"
            if not session_file.exists() and session_id not in known_session_ids:
                lock_file.unlink(missing_ok=True)

    def try_acquire(self, session_id: str, timeout: float = 2.0) -> bool:
        """Try to acquire session lock with short timeout.

        Skips acquisition if locking is disabled. Returns True if lock was
        acquired (or locking is disabled), False if acquisition timed out.

        Args:
            session_id: Unique identifier for the session
            timeout: Maximum time to wait for lock acquisition in seconds

        Returns:
            True if lock acquired or locking disabled, False on timeout
        """
        if self._is_locking_disabled():
            return True
        lock = self._get_or_create_lock(session_id)
        try:
            lock.acquire(timeout=timeout)
            return True
        except FileLockTimeout:
            return False

    def release(self, session_id: str) -> None:
        """Release a previously acquired session lock.

        Args:
            session_id: Unique identifier for the session
        """
        if self._is_locking_disabled():
            return
        lock = self._get_or_create_lock(session_id)
        try:
            lock.release()
        except Exception:
            logger.debug("Failed to release lock for session '%s'", session_id, exc_info=True)
