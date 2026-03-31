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
"""CDP endpoint discovery and validation.

Chrome DevTools Protocol (CDP) is a debugging protocol that allows tools to
instrument, inspect, and debug Chromium-based browsers. Chrome exposes a
WebSocket endpoint (e.g., ws://localhost:9222) that clients connect to for
remote control. This module handles discovering, parsing, and validating
those CDP endpoints.
"""

import logging
import re
import time
from urllib.parse import urlparse, urlunparse

import requests

from nova_act.cli.browser.services.browser_config import DefaultBrowserConfig

logger = logging.getLogger(__name__)

_WS_PREFIX = "ws://"
_WSS_PREFIX = "wss://"
_WS_PREFIXES = (_WS_PREFIX, _WSS_PREFIX)

_MIN_PORT = 1
_MAX_PORT = 65535


def is_websocket_endpoint(endpoint: str) -> bool:
    """Check if endpoint string is a WebSocket URL (ws:// or wss://)."""
    return endpoint.startswith(_WS_PREFIXES)


def validate_port(port: int) -> None:
    """Validate port is in valid TCP range (1-65535).

    Raises:
        ValueError: If port is out of range.
    """
    if port < _MIN_PORT or port > _MAX_PORT:
        raise ValueError(f"Port number must be between {_MIN_PORT} and {_MAX_PORT}, got {port}")


def swap_ws_to_http(endpoint: str) -> str:
    """Convert a WebSocket URL to its HTTP equivalent.

    ws://host:port  -> http://host:port
    wss://host:port -> https://host:port
    """
    return endpoint.replace(_WS_PREFIX, "http://").replace(_WSS_PREFIX, "https://")


class CdpEndpointManager:
    """Discovers, parses, and validates Chrome DevTools Protocol (CDP) endpoints.

    CDP endpoints are WebSocket URLs that Chrome exposes for remote debugging.
    This class provides methods to:
    - Parse user-provided endpoints (port numbers or ws:// URLs)
    - Poll a launched Chrome instance until its CDP endpoint becomes available
    - Validate that an endpoint is reachable and returns a debugger URL
    - Auto-discover running Chrome instances via DevToolsActivePort files or port probing
    """

    def parse_cdp_endpoint(self, cdp_endpoint: str) -> str:
        """Parse CDP endpoint into WebSocket URL format.

        Supports:
        - Port number: "9222" -> "ws://localhost:9222"
        - Full WebSocket URL: "ws://localhost:9222" -> "ws://localhost:9222"

        Args:
            cdp_endpoint: CDP endpoint (port or ws:// URL)

        Returns:
            WebSocket URL in format "ws://host:port"

        Raises:
            ValueError: If endpoint format is invalid
        """
        cdp_endpoint = cdp_endpoint.strip()

        if is_websocket_endpoint(cdp_endpoint):
            return cdp_endpoint

        try:
            port = int(cdp_endpoint)
        except ValueError:
            raise ValueError(
                f"Invalid CDP endpoint format: '{cdp_endpoint}'. "
                "Expected port number (e.g., 9222) or WebSocket URL (e.g., ws://localhost:9222)"
            )
        validate_port(port)
        return f"{_WS_PREFIX}localhost:{port}"

    def extract_port_from_endpoint(self, endpoint: str) -> int | None:
        """Extract port number from WebSocket URL.

        Args:
            endpoint: WebSocket URL (e.g., "ws://localhost:9222")

        Returns:
            Port number or None if not found
        """
        match = re.search(r":(\d+)", endpoint)
        return int(match.group(1)) if match else None

    def _extract_websocket_url(self, url: str, timeout: int) -> str:
        """Extract WebSocket debugger URL from CDP /json/version endpoint.

        Args:
            url: HTTP URL to CDP /json/version endpoint
            timeout: Request timeout in seconds

        Returns:
            WebSocket debugger URL

        Raises:
            requests.RequestException: If request fails
            KeyError: If response missing webSocketDebuggerUrl
        """
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        data: dict[str, object] = response.json()
        return str(data["webSocketDebuggerUrl"])

    def validate_cdp_endpoint(self, endpoint: str) -> str:
        """Validate that CDP endpoint is reachable and return WebSocket debugger URL.

        Converts the ws:// endpoint to http:// to query Chrome's /json/version
        API, which returns the full WebSocket debugger URL for connection.

        Args:
            endpoint: WebSocket URL to validate (e.g., "ws://localhost:9222")

        Returns:
            WebSocket debugger URL from CDP endpoint

        Raises:
            RuntimeError: If endpoint is not reachable or invalid
        """
        http_url = swap_ws_to_http(endpoint)
        # Strip any browser path (e.g., /devtools/browser/abc123) — /json/version
        # must be queried at the root: http://host:port/json/version
        parsed = urlparse(http_url)
        base_url = urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))

        try:
            return self._extract_websocket_url(
                f"{base_url}/json/version",
                DefaultBrowserConfig.CDP_VERSION_CHECK_TIMEOUT_SECONDS,
            )
        except requests.RequestException as e:
            raise RuntimeError(f"CDP endpoint '{endpoint}' is not reachable: {e}")
        except KeyError as e:
            raise RuntimeError(f"CDP endpoint '{endpoint}' did not return webSocketDebuggerUrl") from e

    def get_cdp_endpoint(self, port: int, timeout: int | None = None) -> str:
        """Poll Chrome CDP endpoint until it becomes available.

        Chrome takes a moment to start its CDP server after launch. This method
        repeatedly queries /json/version until a WebSocket URL is returned or
        the timeout expires.

        Args:
            port: CDP port to poll
            timeout: Maximum seconds to wait for endpoint (default: CDP_ENDPOINT_TIMEOUT_SECONDS)

        Returns:
            WebSocket debugger URL

        Raises:
            RuntimeError: If CDP endpoint not available within timeout
        """
        timeout = timeout if timeout is not None else DefaultBrowserConfig.CDP_ENDPOINT_TIMEOUT_SECONDS
        url = f"http://localhost:{port}/json/version"
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                return self._extract_websocket_url(url, DefaultBrowserConfig.CDP_POLL_REQUEST_TIMEOUT_SECONDS)
            except (requests.RequestException, KeyError):
                time.sleep(DefaultBrowserConfig.CDP_ENDPOINT_POLL_INTERVAL_SECONDS)

        raise RuntimeError(f"CDP endpoint not available after {timeout}s")
