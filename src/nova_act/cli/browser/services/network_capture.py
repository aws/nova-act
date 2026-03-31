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
"""Network traffic capture service using Playwright page event listeners.

Establishes the EVENT-LISTENER PATTERN for page-level capture services.
Console capture (Phase 2b) reuses this same pattern.
"""

from __future__ import annotations

import fnmatch
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page, Request, Response

DEFAULT_MAX_ENTRIES = 500


@dataclass
class NetworkEntry:
    """Single captured network request/response pair."""

    url: str
    method: str
    resource_type: str
    timestamp: float
    status: int | None = None
    request_headers: dict[str, str] = field(default_factory=dict)
    response_headers: dict[str, str] = field(default_factory=dict)
    duration_ms: float | None = None
    size: int | None = None
    failed: bool = False
    failure_text: str | None = None


class NetworkCaptureService:
    """Captures network traffic from a Playwright page via event listeners.

    Uses a ring buffer (deque with maxlen) to bound memory usage.
    Designed as a clean template for other event-listener capture services.

    Usage:
        capture = NetworkCaptureService()
        capture.attach(page)
        # ... browser activity ...
        entries = capture.get_entries()
        capture.detach(page)
    """

    def __init__(self, max_entries: int = DEFAULT_MAX_ENTRIES) -> None:
        self._entries: deque[NetworkEntry] = deque(maxlen=max_entries)
        self._entry_index: dict[str, NetworkEntry] = {}  # request_key -> entry for O(1) lookup
        self._pending: dict[str, float] = {}  # request_key -> start_time
        self._attached = False

    @property
    def is_attached(self) -> bool:
        return self._attached

    def attach(self, page: Page) -> None:
        """Register request/response/requestfailed listeners on page."""
        if self._attached:
            return
        page.on("request", self._on_request)
        page.on("response", self._on_response)
        page.on("requestfailed", self._on_request_failed)
        self._attached = True

    def detach(self, page: Page) -> None:
        """Remove listeners from page."""
        if not self._attached:
            return
        page.remove_listener("request", self._on_request)
        page.remove_listener("response", self._on_response)
        page.remove_listener("requestfailed", self._on_request_failed)
        self._attached = False

    def get_entries(
        self,
        *,
        url_filter: str | None = None,
        method: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[NetworkEntry]:
        """Return filtered entries, most recent last.

        Args:
            url_filter: Glob pattern to match against URL (e.g. "*api*").
            method: HTTP method filter (e.g. "GET", "POST").
            status: Status filter — exact code ("200"), range ("4xx", "5xx"),
                    or comparison (">=400").
            limit: Max entries to return (from most recent).
        """
        result = list(self._entries)

        if url_filter:
            result = [e for e in result if fnmatch.fnmatch(e.url, url_filter)]
        if method:
            upper = method.upper()
            result = [e for e in result if e.method == upper]
        if status:
            result = [e for e in result if _matches_status(e.status, status)]
        if limit and limit > 0:
            result = result[-limit:]

        return result

    def clear(self) -> None:
        """Clear all captured entries and pending requests."""
        self._entries.clear()
        self._entry_index.clear()
        self._pending.clear()

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    def _on_request(self, request: Request) -> None:
        key = _request_key(request)
        self._pending[key] = time.monotonic()
        entry = NetworkEntry(
            url=request.url,
            method=request.method,
            resource_type=request.resource_type,
            timestamp=time.time(),
            request_headers=dict(request.headers),
        )
        self._entries.append(entry)
        self._entry_index[key] = entry

    def _on_response(self, response: Response) -> None:
        request = response.request
        key = _request_key(request)
        start = self._pending.pop(key, None)
        duration = (time.monotonic() - start) * 1000 if start is not None else None

        entry = self._entry_index.pop(key, None)
        if entry is not None:
            entry.status = response.status
            entry.response_headers = dict(response.headers)
            entry.duration_ms = round(duration, 1) if duration is not None else None
            content_length = response.headers.get("content-length")
            if content_length:
                try:
                    entry.size = int(content_length)
                except ValueError:
                    pass

    def _on_request_failed(self, request: Request) -> None:
        key = _request_key(request)
        self._pending.pop(key, None)

        entry = self._entry_index.pop(key, None)
        if entry is not None:
            entry.failed = True
            entry.failure_text = request.failure


def _request_key(request: Request) -> str:
    """Unique key for matching request to response."""
    return f"{request.method}:{request.url}:{id(request)}"


def _matches_status(actual: int | None, pattern: str) -> bool:
    """Check if a status code matches a filter pattern.

    Supports: exact ("200"), range ("4xx", "5xx"), comparison (">=400").
    """
    if actual is None:
        return False
    if pattern.endswith("xx"):
        try:
            prefix = int(pattern[0])
            return actual // 100 == prefix
        except (ValueError, IndexError):
            return False
    if pattern.startswith(">="):
        try:
            return actual >= int(pattern[2:])
        except ValueError:
            return False
    try:
        return actual == int(pattern)
    except ValueError:
        return False
