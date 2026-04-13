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
"""Browser cookie provider base class."""

from abc import ABC, abstractmethod

from playwright._impl._api_structures import SetCookieParam


class BrowserCookieProvider(ABC):
    """Abstract base class for browser cookie providers.

    Customers can extend this class to provide custom authentication
    cookies for their browser sessions. The provider is responsible for
    loading cookies that will be injected into the browser context.

    For full session persistence (save and restore browser state across
    sessions), use ``BrowserSessionProvider`` instead.

    Example:
        >>> from nova_act import NovaAct
        >>> from nova_act.browser_auth import BrowserCookieProvider
        >>> from playwright._impl._api_structures import SetCookieParam
        >>>
        >>> class MyCustomAuth(BrowserCookieProvider):
        ...     @property
        ...     def name(self) -> str:
        ...         return "MyCustomAuth"
        ...
        ...     def load_cookies(self) -> list[SetCookieParam]:
        ...         # Load cookies from your custom source
        ...         return [{"name": "session", "value": "...", "domain": ".example.com", "path": "/"}]
        >>>
        >>> with NovaAct(
        ...     starting_page="https://example.com",
        ...     browser_auth=MyCustomAuth()
        ... ) as nova:
        ...     nova.act("Navigate to the page")
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for logging purposes."""

    @abstractmethod
    def load_cookies(self) -> list[SetCookieParam]:
        """Load authentication cookies to inject into the browser.

        Returns:
            List of cookies in Playwright's SetCookieParam format.

        Raises:
            BrowserAuthError: If authentication fails or cookies cannot be loaded.
        """
