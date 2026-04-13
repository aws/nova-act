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
"""Local file-based browser session provider.

Persists browser storage state as a JSON file on disk.
"""

from __future__ import annotations

import json
import logging
import os
import stat
from pathlib import Path

from playwright.sync_api import StorageState

from nova_act.browser_auth.browser_session_provider import BrowserSessionProvider
from nova_act.types.errors import BrowserAuthError

_LOGGER = logging.getLogger(__name__)


class LocalFileSessionProvider(BrowserSessionProvider):
    """Browser session provider backed by local JSON files.

    Stores the browser storage state (cookies and localStorage)
    as a JSON file on disk. Files are written atomically
    with restricted permissions (0o600, owner read/write only).

    Suitable for development, testing, and single-machine agent
    workflows. For multi-machine or production use, prefer
    ``S3SessionProvider`` or ``AgentCoreBrowserSessionProvider``.

    Example:
        >>> from nova_act import NovaAct
        >>> from nova_act.browser_auth import LocalFileSessionProvider
        >>>
        >>> provider = LocalFileSessionProvider(profile="my-app")
        >>> with NovaAct(
        ...     starting_page="https://example.com",
        ...     browser_auth=provider,
        ... ) as nova:
        ...     nova.act("Do something")

    Args:
        directory: Base directory for session files. Supports ``~``
            expansion. Defaults to ``~/.nova-act/sessions``.
        profile: Session profile name. Used as the filename
            (``{profile}.json``). Defaults to ``"default"``.
    """

    def __init__(
        self,
        directory: str | Path = "~/.nova-act/sessions",
        profile: str = "default",
    ) -> None:
        self._directory = Path(directory).expanduser()
        self._profile = profile
        self._path = self._directory / f"{profile}.json"

    @property
    def name(self) -> str:
        return "LocalFileSessionProvider"

    def load_storage_state(self) -> StorageState | None:
        """Load storage state from a local JSON file.

        Returns:
            The storage state dict, or ``None`` if the file does
            not exist.

        Raises:
            BrowserAuthError: If the file exists but cannot be read
                or contains invalid JSON.
        """
        try:
            text = self._path.read_text(encoding="utf-8")
            state: StorageState = json.loads(text)
            _LOGGER.info("Loaded session state from %s", self._path)
            return state
        except FileNotFoundError:
            _LOGGER.debug("No saved session at %s", self._path)
            return None
        except json.JSONDecodeError as exc:
            raise BrowserAuthError(f"Corrupted session data at {self._path}: {exc}") from exc
        except Exception as exc:
            raise BrowserAuthError(f"Failed to load session from {self._path}: {exc}") from exc

    def save_storage_state(self, state: StorageState) -> None:
        """Save storage state to a local JSON file.

        Creates parent directories as needed. Sets file permissions
        to ``0o600`` (owner read/write only).

        Raises:
            BrowserAuthError: If the file cannot be written.
        """
        try:
            self._directory.mkdir(parents=True, exist_ok=True)

            # Write to a temp file and rename for atomicity
            tmp_path = self._path.with_suffix(".json.tmp")
            tmp_path.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
            os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
            tmp_path.replace(self._path)

            _LOGGER.info("Saved session state to %s", self._path)
        except Exception as exc:
            raise BrowserAuthError(f"Failed to save session to {self._path}: {exc}") from exc
