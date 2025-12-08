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
"""State manager for per-region workflow state files."""

import json
import logging
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from nova_act.cli.core.config import (
    get_account_dir,
    get_region_dir,
    get_state_dir,
    get_state_file_path,
)
from nova_act.cli.core.error_detection import (
    get_state_corrupted_message,
    get_state_write_failed_message,
)
from nova_act.cli.core.exceptions import ConfigurationError
from nova_act.cli.core.types import RegionState, StateLockInfo, WorkflowInfo

logger = logging.getLogger(__name__)


class StateLock:
    """File-based locking for state operations."""

    def __init__(self, account_id: str, region: str):
        self.lock_info = StateLockInfo(lock_file=str(get_state_dir() / f"{account_id}-{region}.lock"), timeout=30)

    def __enter__(self) -> "StateLock":
        """Acquire lock with timeout."""
        return self._acquire_lock_with_timeout()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:  # type: ignore[explicit-any]
        """Release lock."""
        try:
            Path(self.lock_info.lock_file).unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Failed to release lock: {e}")

    def _acquire_lock_with_timeout(self) -> "StateLock":
        """Acquire lock with timeout and retry logic."""
        start_time = time.time()
        lock_file = Path(self.lock_info.lock_file)

        # Ensure state directory exists
        get_state_dir().mkdir(exist_ok=True)

        while time.time() - start_time < self.lock_info.timeout:
            try:
                lock_file.touch(exist_ok=False)
                return self
            except FileExistsError:
                time.sleep(0.1)

        raise ConfigurationError(f"Could not acquire lock: {self.lock_info.lock_file}")


class StateManager:
    """Manages per-region workflow state files."""

    def __init__(self, account_id: str, region: str):
        """Initialize StateManager for specific account and region."""
        if not account_id or not account_id.strip():
            raise ValueError("account_id cannot be empty or None")
        if not region or not region.strip():
            raise ValueError("region cannot be empty or None")

        self.account_id = account_id
        self.region = region

    def get_region_state(self) -> RegionState:
        """Load state for current account/region."""
        state_file = self._get_workflow_state_file_path()

        if not state_file.exists():
            return RegionState()

        try:
            with open(state_file) as f:
                data = json.load(f)
            return self._load_region_state(data)
        except Exception as e:
            message = get_state_corrupted_message(state_file=state_file, error=str(e))
            raise ConfigurationError(message)

    def save_region_state(self, state: RegionState) -> None:
        """Save state for current account/region with locking."""
        with StateLock(account_id=self.account_id, region=self.region):
            self._ensure_state_dir()
            state_file = self._get_workflow_state_file_path()

            # Update timestamp
            state.last_updated = datetime.now()

            # Atomic write
            self._write_state_to_temp_file(state_file=state_file, state=state)

    def list_workflows(self) -> List[WorkflowInfo]:
        """List workflows in current region."""
        state = self.get_region_state()
        return list(state.workflows.values())

    def cleanup_account(self) -> None:
        """Remove all state for current account."""
        account_dir = get_account_dir(self.account_id)
        if account_dir.exists():
            shutil.rmtree(account_dir)
            logger.info(f"Cleaned up state for account: {self.account_id}")

    def cleanup_region(self) -> None:
        """Remove state for current account/region."""
        self._cleanup_workflow_state()

    def _cleanup_workflow_state(self) -> None:
        """Remove state for current account/region."""
        state_file = self._get_workflow_state_file_path()
        if state_file.exists():
            state_file.unlink()
            logger.info(f"Cleaned up state for account: {self.account_id}, region: {self.region}")

    def _get_workflow_state_file_path(self) -> Path:
        """Get path to state file for current account/region."""
        return get_state_file_path(account_id=self.account_id, region=self.region)

    def _ensure_state_dir(self) -> None:
        """Ensure state directory structure exists."""
        get_state_dir().mkdir(exist_ok=True)
        get_account_dir(account_id=self.account_id).mkdir(exist_ok=True)
        get_region_dir(account_id=self.account_id, region=self.region).mkdir(exist_ok=True)

    def _write_state_to_temp_file(self, state_file: Path, state: RegionState) -> None:
        """Write state to temporary file and atomically move to final location."""
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", dir=state_file.parent, delete=False, suffix=".tmp") as f:
                temp_file = f.name
                data = self._convert_state_to_dict(state)
                json.dump(obj=data, fp=f, indent=2, default=str)

            shutil.move(src=temp_file, dst=state_file)
        except Exception as e:
            if temp_file and Path(temp_file).exists():
                Path(temp_file).unlink()
            message = get_state_write_failed_message(state_file=state_file, error=str(e))
            raise ConfigurationError(message)

    @staticmethod
    def _load_region_state(data: Dict[str, Any]) -> RegionState:  # type: ignore[explicit-any]
        """Load RegionState from dictionary."""
        return RegionState.model_validate(data)

    @staticmethod
    def _convert_state_to_dict(state: RegionState) -> Dict[str, Any]:  # type: ignore[explicit-any]
        """Convert RegionState to dictionary."""
        return state.model_dump()
