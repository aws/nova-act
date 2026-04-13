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
"""Browser authentication utilities for NovaAct.

This module provides authentication support for browser sessions.

Cookie-only provider:
    >>> from nova_act.browser_auth import BrowserCookieProvider
    >>> from playwright._impl._api_structures import SetCookieParam
    >>>
    >>> class MyAuth(BrowserCookieProvider):
    ...     @property
    ...     def name(self) -> str:
    ...         return "MyAuth"
    ...     def load_cookies(self) -> list[SetCookieParam]:
    ...         return [{"name": "session", "value": "...", "domain": ".example.com", "path": "/"}]

Session persistence with a built-in provider:
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

from typing import TypeAlias

from playwright.sync_api import StorageState

from nova_act.browser_auth.agentcore_session_provider import AgentCoreBrowserSessionProvider
from nova_act.browser_auth.browser_cookie_provider import BrowserCookieProvider
from nova_act.browser_auth.browser_session_provider import BrowserSessionProvider
from nova_act.browser_auth.local_file_session_provider import LocalFileSessionProvider
from nova_act.browser_auth.s3_session_provider import S3SessionProvider

# isort: off
# isort: on

# Union type for browser authentication
BrowserAuth: TypeAlias = BrowserCookieProvider | None

__all__ = [
    "AgentCoreBrowserSessionProvider",
    "BrowserAuth",
    "BrowserCookieProvider",
    "BrowserSessionProvider",
    "LocalFileSessionProvider",
    "S3SessionProvider",
    "StorageState",
]
