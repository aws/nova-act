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
"""Browser session provider base class.

Extends BrowserCookieProvider with full storage state save/load
support for session persistence across browser sessions.
"""

from __future__ import annotations

import json
import logging
from abc import abstractmethod
from typing import cast

from playwright._impl._api_structures import OriginState, SetCookieParam
from playwright.sync_api import StorageState

from nova_act.browser_auth.browser_cookie_provider import BrowserCookieProvider

_LOGGER = logging.getLogger(__name__)


class BrowserSessionProvider(BrowserCookieProvider):
    """Browser session provider with save/load support.

    Extends ``BrowserCookieProvider`` to capture and restore browser
    storage state (cookies and localStorage) across sessions. The SDK
    calls ``save_session()`` when the browser stops and
    ``load_cookies()`` on the next start to restore cookies.

    **Client-side providers** (``LocalFileSessionProvider``,
    ``S3SessionProvider``) implement ``load_storage_state()`` and
    ``save_storage_state()`` for their storage backend. The default
    ``save_session()`` delegates to ``save_storage_state()``.

    **Server-side providers** (``AgentCoreBrowserSessionProvider``) override
    ``save_session()`` to call their persistence API directly,
    ignoring the provided state since it is persisted server-side.

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
        ...     # Session state is saved automatically on exit
    """

    def __init__(self, *, restore_local_storage: bool = False) -> None:
        self._session_cache: StorageState | None = None
        self.restore_local_storage = restore_local_storage

    @abstractmethod
    def load_storage_state(self) -> StorageState | None:
        """Load previously saved storage state.

        Returns:
            The storage state dict (cookies and localStorage),
            or ``None`` if no saved state exists.

        Raises:
            BrowserAuthError: If the storage backend is unreachable
                or the saved state is corrupted.
        """

    @abstractmethod
    def save_storage_state(self, state: StorageState) -> None:
        """Persist the browser storage state to the backend.

        Called by the default ``save_session()`` implementation after
        it captures state from the Playwright context. Each subclass
        controls how and where the data is persisted (e.g., local
        file with 0o600 permissions, S3 with SSE-KMS encryption).

        Server-side providers that override ``save_session()`` may
        still implement this as a no-op or fallback.

        Args:
            state: The storage state dict containing cookies
                and localStorage.

        Raises:
            BrowserAuthError: If the state cannot be saved.
        """

    def save_session(self, state: StorageState) -> None:
        """Persist the captured storage state.

        Called by the SDK when the browser stops, after capturing
        storage state from the Playwright context. The default
        implementation delegates to ``save_storage_state()`` and then
        invalidates the session cache so that a reused provider instance
        loads fresh state on the next session start.

        Server-side providers (e.g., ``AgentCoreBrowserSessionProvider``)
        override this to call their persistence API directly,
        ignoring the provided state since it is persisted
        server-side.

        Args:
            state: The storage state dict (cookies and localStorage)
                captured from the Playwright context.

        Raises:
            BrowserAuthError: If the state cannot be saved.
        """
        try:
            self.save_storage_state(state)
        finally:
            self._session_cache = None

    @staticmethod
    def make_local_storage_init_script(local_storage: list[OriginState]) -> str:
        """Build a Playwright init script that restores localStorage entries.

        The script runs on every page before any page scripts execute, checks
        whether the current origin matches a saved entry, and calls
        ``localStorage.setItem`` for each key-value pair.

        Args:
            local_storage: The ``origins`` array from a Playwright
                ``StorageState``, where each entry has an ``origin`` URL
                and a ``localStorage`` list of ``{"name": ..., "value": ...}``
                pairs.

        Returns:
            A self-contained JavaScript IIFE suitable for
            ``context.add_init_script()``.
        """
        return f"""(function() {{
            var entries = {json.dumps(local_storage)};
            var match = entries.find(function(e) {{
                return e.origin === window.location.origin;
            }});
            if (match) {{
                (match.localStorage || []).forEach(function(item) {{
                    if (window.localStorage.getItem(item.name) === null) {{
                        window.localStorage.setItem(item.name, item.value);
                    }}
                }});
            }}
        }})();"""

    def _load_session(self) -> StorageState:
        """Load cookies and localStorage from the saved storage state.

        Calls ``load_storage_state()`` once per instance and caches the
        result, so ``load_cookies()`` and ``load_local_storage()`` can
        each delegate here without incurring extra round-trips to the
        storage backend.

        Returns:
            A ``StorageState`` with ``cookies`` and ``origins`` populated
            from the saved state, or empty lists if no saved state exists.
        """
        if self._session_cache is not None:
            return self._session_cache
        state: StorageState | None = self.load_storage_state()
        self._session_cache = state if state is not None else StorageState()
        return self._session_cache

    def load_cookies(self) -> list[SetCookieParam]:
        """Extract cookies from the saved storage state.

        Convenience wrapper around ``_load_session()``. Use
        ``_load_session()`` directly when you also need localStorage.
        """
        # StorageStateCookie and SetCookieParam are structurally
        # compatible TypedDicts (same fields), but mypy treats them
        # as distinct nominal types.
        return cast(list[SetCookieParam], self._load_session().get("cookies", []))

    def load_local_storage(self) -> list[OriginState]:
        """Extract localStorage origins from the saved storage state.

        Convenience wrapper around ``_load_session()``. Only called by
        the SDK when ``restore_local_storage=True``.

        localStorage restoration is opt-in (``restore_local_storage=False``
        by default) because most auth flows rely on cookies alone.
        Enable it only when the app stores session-critical data in
        localStorage (e.g. JWTs or refresh tokens written at login).

        .. warning::
            localStorage is restored via Playwright's
            ``context.add_init_script()``, which runs on **every page
            navigation**, not only the first. The script uses a
            merge strategy: snapshot values are only written for keys
            that do not already exist in localStorage, so mid-session
            writes are preserved across navigations. The one remaining
            edge case is that if the app explicitly deletes a key during
            the session, that key will be re-added from the snapshot on
            the next navigation.
        """
        return self._load_session().get("origins", [])
