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

import logging
from abc import abstractmethod
from typing import cast

from playwright._impl._api_structures import SetCookieParam
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
        implementation delegates to ``save_storage_state()``.

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
        self.save_storage_state(state)

    def load_cookies(self) -> list[SetCookieParam]:
        """Extract cookies from the saved storage state.

        Default implementation that provides backward compatibility
        with the SDK's existing cookie injection code. Subclasses
        can override this if they need custom cookie extraction.
        """
        state = self.load_storage_state()
        if state is None:
            return []
        # StorageStateCookie and SetCookieParam are structurally
        # compatible TypedDicts (same fields), but mypy treats them
        # as distinct nominal types.
        return cast(list[SetCookieParam], state.get("cookies", []))
