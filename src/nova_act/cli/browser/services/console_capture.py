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
"""Console message capture service using Playwright page event listeners.

Follows the EVENT-LISTENER PATTERN established by network_capture.py.
Uses page.on('console') and page.on('pageerror') to capture browser console output.
"""

from __future__ import annotations

import fnmatch
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import ConsoleMessage, Error, Page

DEFAULT_MAX_ENTRIES = 500


@dataclass
class ConsoleEntry:
    """Single captured console message or page error."""

    level: str  # log, warning, error, info, debug, trace, pageerror
    text: str
    timestamp: float
    source_url: str | None = None
    line_number: int | None = None
    column_number: int | None = None
    args: list[str] = field(default_factory=list)


class ConsoleCaptureService:
    """Captures console messages and page errors from a Playwright page.

    Uses a ring buffer (deque with maxlen) to bound memory usage.
    Mirrors NetworkCaptureService's attach/detach/get_entries/clear API.

    Usage:
        capture = ConsoleCaptureService()
        capture.attach(page)
        # ... browser activity ...
        entries = capture.get_entries()
        capture.detach(page)
    """

    def __init__(self, max_entries: int = DEFAULT_MAX_ENTRIES) -> None:
        self._entries: deque[ConsoleEntry] = deque(maxlen=max_entries)
        self._attached = False

    @property
    def is_attached(self) -> bool:
        return self._attached

    def attach(self, page: Page) -> None:
        """Register console and pageerror listeners on page."""
        if self._attached:
            return
        page.on("console", self._on_console)
        page.on("pageerror", self._on_pageerror)
        self._attached = True

    def detach(self, page: Page) -> None:
        """Remove listeners from page."""
        if not self._attached:
            return
        page.remove_listener("console", self._on_console)
        page.remove_listener("pageerror", self._on_pageerror)
        self._attached = False

    def get_entries(
        self,
        *,
        level: str | None = None,
        text_filter: str | None = None,
        errors_only: bool = False,
        limit: int | None = None,
    ) -> list[ConsoleEntry]:
        """Return filtered entries, most recent last.

        Args:
            level: Filter by console level (log, warning, error, info, debug, pageerror).
            text_filter: Glob pattern to match against message text.
            errors_only: Shortcut to filter to error + pageerror only.
            limit: Max entries to return (from most recent).
        """
        result = list(self._entries)

        if errors_only:
            result = [e for e in result if e.level in ("error", "pageerror")]
        elif level:
            result = [e for e in result if e.level == level]
        if text_filter:
            result = [e for e in result if fnmatch.fnmatch(e.text, text_filter)]
        if limit and limit > 0:
            result = result[-limit:]

        return result

    def clear(self) -> None:
        """Clear all captured entries."""
        self._entries.clear()

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    def _on_console(self, msg: ConsoleMessage) -> None:
        location = msg.location
        entry = ConsoleEntry(
            level=msg.type,
            text=msg.text,
            timestamp=time.time(),
            source_url=location.get("url") if location else None,
            line_number=location.get("lineNumber") if location else None,
            column_number=location.get("columnNumber") if location else None,
        )
        self._entries.append(entry)

    def _on_pageerror(self, error: Error) -> None:
        entry = ConsoleEntry(
            level="pageerror",
            text=str(error),
            timestamp=time.time(),
        )
        self._entries.append(entry)
