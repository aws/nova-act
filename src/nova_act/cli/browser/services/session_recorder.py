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
"""Session recorder — automatic manifest of every command executed in a session."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime
from typing import TypedDict

from typing_extensions import NotRequired

from nova_act.cli.browser.utils.log_capture import get_log_dir


class CommandEntry(TypedDict, total=False):
    """A single command recorded in the session manifest."""

    command: str
    type: str
    args: dict[str, object]
    timestamp: str
    duration_ms: float
    result_summary: dict[str, object]
    screenshots: dict[str, str | None]
    log_file: str
    steps_file: str
    steps_summary: object
    screenshots_base64: dict[str, str]
    result: dict[str, object]


class SessionManifest(TypedDict):
    """Top-level session recording manifest."""

    session_id: str
    started_at: str
    commands: list[CommandEntry]
    last_updated: NotRequired[str]


logger = logging.getLogger(__name__)

MANIFEST_FILENAME = "recording.json"


class SessionRecorder:
    """Records every command invocation in a session as a JSON manifest.

    The manifest is written to the session's log directory and updated
    after each command completes. No explicit start/stop — recording is
    always active.
    """

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._log_dir = get_log_dir(session_id)
        self._manifest_path = self._log_dir / MANIFEST_FILENAME
        self._manifest: SessionManifest = self._load_or_create()

    def _load_or_create(self) -> SessionManifest:
        """Load existing manifest or create a new one."""
        if self._manifest_path.exists():
            try:
                data: SessionManifest = json.loads(self._manifest_path.read_text())
                return data
            except (json.JSONDecodeError, OSError):
                logger.debug("Corrupt manifest at %s, creating new", self._manifest_path)
        return SessionManifest(
            session_id=self.session_id,
            started_at=datetime.now().isoformat(),
            commands=[],
        )

    def record_step(
        self,
        command_name: str,
        args: dict[str, object] | None = None,
        started_at: datetime | None = None,
        duration_ms: float | None = None,
        result_summary: dict[str, object] | None = None,
        screenshots: dict[str, str | None] | None = None,
        log_file: str | None = None,
        steps_file: str | None = None,
    ) -> None:
        """Append a command entry to the manifest and persist to disk."""
        entry: CommandEntry = {
            "command": command_name,
            "args": args or {},
            "timestamp": (started_at or datetime.now()).isoformat(),
        }
        if duration_ms is not None:
            entry["duration_ms"] = round(duration_ms, 1)
        if result_summary:
            entry["result_summary"] = result_summary
        if screenshots:
            entry["screenshots"] = {k: v for k, v in screenshots.items() if v}
        if log_file:
            entry["log_file"] = log_file
        if steps_file:
            entry["steps_file"] = steps_file

        self._manifest["commands"].append(entry)
        self._manifest["last_updated"] = datetime.now().isoformat()
        self._persist()

    def get_manifest(self) -> SessionManifest:
        """Return the current manifest."""
        return self._manifest

    def get_commands(self, limit: int | None = None) -> list[CommandEntry]:
        """Return recorded commands, optionally limited to last N."""
        commands = self._manifest["commands"]
        if limit is not None and limit > 0:
            return commands[-limit:]
        return commands

    def _persist(self) -> None:
        """Atomically write manifest to disk."""
        self._log_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=str(self._log_dir), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._manifest, f, indent=2)
            os.replace(tmp_path, str(self._manifest_path))
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise


# Module-level registry: session_id → SessionRecorder
_recorder_registry: dict[str, SessionRecorder] = {}


def get_recorder(session_id: str) -> SessionRecorder:
    """Get or create a SessionRecorder for the given session."""
    if session_id not in _recorder_registry:
        _recorder_registry[session_id] = SessionRecorder(session_id)
    return _recorder_registry[session_id]
