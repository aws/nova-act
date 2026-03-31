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
"""File-based locking utilities for Nova Act CLI."""

import os
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock
from filelock import Timeout as FileLockTimeout

from nova_act.cli.core.exceptions import SessionLockTimeout

# Default lock timeout in seconds
DEFAULT_LOCK_TIMEOUT_SECONDS = 30.0


class FileLockManager:
    """Manages file-based locks for thread-safe operations.

    Provides locking using file-based locks to prevent
    concurrent modifications to the same resource.

    Primary consumer: browser/services/session/locking.py (SessionLockManager).
    """

    def __init__(self, lock_dir: Path, default_timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS):
        """Initialize the file lock manager.

        Args:
            lock_dir: Directory where lock files are stored
            default_timeout: Default timeout for lock acquisition in seconds
        """
        self.lock_dir = lock_dir
        self.default_timeout = default_timeout
        self._locks: dict[str, FileLock] = {}

    def _lock_file_path(self, resource_id: str) -> Path:
        """Get path to lock file.

        Args:
            resource_id: Unique identifier for the resource

        Returns:
            Path to lock file
        """
        return self.lock_dir / f"{resource_id}.lock"

    def get_lock_file_path(self, resource_id: str) -> Path:
        """Get path to lock file for a resource.

        Args:
            resource_id: Unique identifier for the resource

        Returns:
            Path to lock file
        """
        return self._lock_file_path(resource_id)

    def remove_lock(self, resource_id: str) -> None:
        """Remove lock from memory and delete lock file from filesystem.

        Args:
            resource_id: Unique identifier for the resource to unlock
        """
        if resource_id in self._locks:
            del self._locks[resource_id]

        lock_path = self._lock_file_path(resource_id)
        if lock_path.exists():
            lock_path.unlink()

    def _get_or_create_lock(self, resource_id: str) -> FileLock:
        """Get existing lock or create new one for resource.

        Args:
            resource_id: Unique identifier for the resource

        Returns:
            FileLock for the resource
        """
        if resource_id not in self._locks:
            lock_path = self._lock_file_path(resource_id)
            self._locks[resource_id] = FileLock(str(lock_path))
        return self._locks[resource_id]

    def _is_locking_disabled(self) -> bool:
        """Check if locking is disabled for testing.

        Returns:
            True if locking is disabled via environment variable
        """
        return os.environ.get("NOVA_ACT_DISABLE_SESSION_LOCK") == "1"

    def _acquire_lock_with_timeout(self, lock: FileLock, resource_id: str, timeout: float) -> None:
        """Acquire file lock with timeout handling.

        Args:
            lock: FileLock to acquire
            resource_id: Resource identifier for error messages
            timeout: Maximum time to wait for lock acquisition

        Raises:
            SessionLockTimeout: If lock cannot be acquired within timeout
        """
        try:
            lock.acquire(timeout=timeout)
        except FileLockTimeout:
            raise SessionLockTimeout(f"Resource '{resource_id}' is busy. Another operation is in progress.")

    @contextmanager
    def with_lock(
        self,
        resource_id: str,
        exists_check: Callable[[str], None],
        timeout: float | None = None,
    ) -> Generator[None, None, None]:
        """Context manager for file-based locking.

        Args:
            resource_id: Unique identifier for the resource
            exists_check: Callable that raises KeyError if resource doesn't exist
            timeout: Maximum time to wait for lock acquisition in seconds

        Yields:
            None (lock is held during context)

        Raises:
            KeyError: If resource does not exist
            SessionLockTimeout: If lock cannot be acquired within timeout
        """
        if self._is_locking_disabled():
            yield
            return

        exists_check(resource_id)
        lock = self._get_or_create_lock(resource_id)
        effective_timeout = timeout if timeout is not None else self.default_timeout

        self._acquire_lock_with_timeout(lock, resource_id, effective_timeout)

        try:
            yield
        finally:
            lock.release()
