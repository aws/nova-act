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
"""Session persistence module for managing session metadata storage.

This module handles all file-based session metadata operations including:
- Creating and managing session directory
- Reading/writing session metadata to JSON files
- Loading existing sessions from disk on startup
"""

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from nova_act.cli.browser.services.session.models import (
    SessionInfo,
    SessionState,
)
from nova_act.cli.core.process import is_process_running


class _MetadataFields(TypedDict):
    """Typed fields extracted from session metadata for SessionInfo construction."""

    last_used: str | None
    user_data_dir: str | None
    cdp_port: int | None
    active_tab_index: int
    error_message: str | None
    browser_options_meta: dict[str, object]


logger = logging.getLogger(__name__)

# Secure directory permissions: owner read/write/execute only
SESSION_DIR_PERMISSIONS = 0o700


class SessionPersistence:
    """Manages file-based session metadata storage and retrieval."""

    def __init__(self, session_dir: str):
        """Initialize session persistence manager.

        Args:
            session_dir: Directory path for storing session metadata files
        """
        self.session_dir = session_dir
        self._ensure_session_directory()

    def _ensure_session_directory(self) -> None:
        """Create session directory if it doesn't exist with secure permissions."""
        session_path = Path(self.session_dir)
        if not session_path.exists():
            session_path.mkdir(parents=True, mode=SESSION_DIR_PERMISSIONS, exist_ok=True)
        else:
            # Ensure correct permissions on existing directory
            os.chmod(self.session_dir, SESSION_DIR_PERMISSIONS)

    def get_session_file_path(self, session_id: str) -> Path:
        """Get path to session metadata file.

        Args:
            session_id: Unique identifier for the session

        Returns:
            Path to session JSON file
        """
        return Path(self.session_dir) / f"{session_id}.json"

    def write_session_metadata(self, session_info: SessionInfo) -> None:
        """Write session metadata to JSON file.

        Args:
            session_info: SessionInfo object to serialize
        """
        metadata = session_info.to_dict()

        file_path = self.get_session_file_path(session_info.session_id)
        fd, tmp_path = tempfile.mkstemp(dir=str(file_path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)
            os.replace(tmp_path, file_path)
        except BaseException:
            os.unlink(tmp_path)
            raise

    def read_session_metadata(self, session_id: str) -> dict[str, object]:
        """Read session metadata from JSON file.

        Args:
            session_id: Unique identifier for the session

        Returns:
            Dictionary containing session metadata

        Raises:
            FileNotFoundError: If session file doesn't exist
            json.JSONDecodeError: If session file is corrupted
        """
        file_path = self.get_session_file_path(session_id)
        with open(file_path, "r", encoding="utf-8") as f:
            result: dict[str, object] = json.load(f)
            return result

    def load_session(self, session_id: str) -> SessionInfo:
        """Load a single session from disk by ID.

        Args:
            session_id: Unique identifier for the session

        Returns:
            SessionInfo object with nova_act_instance=None (state determined by PID liveness)

        Raises:
            FileNotFoundError: If session file doesn't exist
            json.JSONDecodeError: If session file is corrupted
            KeyError: If required metadata fields are missing
            ValueError: If metadata values are invalid
        """
        metadata = self.read_session_metadata(session_id)
        return self._reconstruct_session_from_metadata(metadata)

    def _reconstruct_session_from_metadata(self, metadata: dict[str, object]) -> SessionInfo:
        """Reconstruct SessionInfo from metadata dictionary.

        Determines session state by checking if the browser process is still running
        and whether the CDP endpoint is responsive.

        Args:
            metadata: Dictionary containing session metadata

        Returns:
            SessionInfo object with nova_act_instance=None
        """
        raw_pid = metadata.get("browser_pid")
        browser_pid = int(raw_pid) if isinstance(raw_pid, (int, float)) else None
        cdp_endpoint_raw = metadata.get("cdp_endpoint")

        # Determine state
        state = self._determine_session_state(browser_pid)

        # Extract remaining fields
        fields = self._extract_metadata_fields(metadata)

        return SessionInfo(
            session_id=str(metadata["session_id"]),
            state=state,
            nova_act_instance=None,
            created_at=datetime.fromisoformat(str(metadata["created_at"])),
            browser_pid=browser_pid,
            user_data_dir=fields["user_data_dir"],
            last_used=datetime.fromisoformat(fields["last_used"]) if fields["last_used"] else None,
            cdp_endpoint=str(cdp_endpoint_raw) if cdp_endpoint_raw is not None else None,
            cdp_port=fields["cdp_port"],
            error_message=fields["error_message"],
            browser_options_meta=fields["browser_options_meta"],
            auth_config=None,  # Auth resolved fresh each invocation (GAP-5)
            active_tab_index=fields["active_tab_index"],
        )

    @staticmethod
    def _determine_session_state(
        browser_pid: int | None,
    ) -> SessionState:
        """Determine session state from browser PID liveness.

        Args:
            browser_pid: Browser process ID, or None if unknown.

        Returns:
            STARTED if PID is alive, STOPPED otherwise.
        """
        if browser_pid is None or not is_process_running(browser_pid):
            return SessionState.STOPPED

        return SessionState.STARTED

    @staticmethod
    def _extract_metadata_fields(metadata: dict[str, object]) -> _MetadataFields:
        """Extract and normalize optional metadata fields.

        Returns:
            Dictionary with normalized field values ready for SessionInfo construction.
        """
        last_used_raw = metadata.get("last_used")
        user_data_dir_raw = metadata.get("user_data_dir")
        cdp_port_raw = metadata.get("cdp_port")
        active_tab_index_raw = metadata.get("active_tab_index", 0)

        meta_dict = metadata.get("metadata", {})
        meta_dict = meta_dict if isinstance(meta_dict, dict) else {}
        error_message_raw = meta_dict.get("error_message")
        browser_options_raw = meta_dict.get("browser_options")

        return {
            "last_used": str(last_used_raw) if last_used_raw else None,
            "user_data_dir": str(user_data_dir_raw) if user_data_dir_raw is not None else None,
            "cdp_port": int(cdp_port_raw) if isinstance(cdp_port_raw, (int, float)) else None,
            "active_tab_index": int(active_tab_index_raw) if isinstance(active_tab_index_raw, (int, float)) else 0,
            "error_message": str(error_message_raw) if error_message_raw else None,
            "browser_options_meta": browser_options_raw if isinstance(browser_options_raw, dict) else {},
        }

    def read_used_ports(self, exclude_ids: set[str]) -> set[int]:
        """Read CDP port numbers from session metadata files without loading full sessions.

        Args:
            exclude_ids: Session IDs to skip (already in memory)

        Returns:
            Set of port numbers in use by persisted sessions
        """
        session_dir = Path(self.session_dir)
        if not session_dir.exists():
            return set()

        ports: set[int] = set()
        for session_file in session_dir.glob("*.json"):
            if session_file.stem in exclude_ids:
                continue
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                    if port := metadata.get("cdp_port"):
                        ports.add(port)
            except (json.JSONDecodeError, OSError):
                continue
        return ports

    def load_existing_sessions(self, existing_session_ids: set[str]) -> dict[str, SessionInfo]:
        """Load existing sessions from disk.

        Discovers session metadata files in session_dir and reconstructs
        SessionInfo objects. Handles corrupted files gracefully by logging
        warnings and skipping them.

        Args:
            existing_session_ids: Set of session IDs already in memory (to skip)

        Returns:
            Dictionary mapping session_id to SessionInfo for loaded sessions

        Note: Only loads sessions that don't already exist in memory to avoid
        overwriting active sessions with nova_act_instance=None.

        Session state is determined by checking if the browser PID is still alive.
        """
        session_dir = Path(self.session_dir)
        if not session_dir.exists():
            return {}

        session_files = [f for f in session_dir.glob("*.json") if f.stem not in existing_session_ids]

        loaded_sessions: dict[str, SessionInfo] = {}
        for session_file in session_files:
            session_id = session_file.stem
            try:
                metadata = self.read_session_metadata(session_id)
                session_info = self._reconstruct_session_from_metadata(metadata)
                loaded_sessions[session_info.session_id] = session_info
            except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning("Failed to load session '%s': %s", session_id, e)

        return loaded_sessions
