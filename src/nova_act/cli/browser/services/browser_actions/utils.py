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
"""Shared utilities for composite browser commands."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from playwright.sync_api import Error as PlaywrightError
from pydantic import BaseModel

from nova_act.cli.browser.services.intent_resolution.snapshot import (
    SnapshotElement,
    flatten_snapshot,
)
from nova_act.util.jsonschema import BOOL_SCHEMA

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from nova_act import NovaAct

logger = logging.getLogger(__name__)

__all__ = [
    "BOOL_SCHEMA",
    "OBSERVE_PROMPT",
    "ObserveSchema",
    "TransitionTracker",
    "build_prompt_with_focus",
    "generate_fast_transition",
    "generate_structured_transition",
    "get_page_context",
    "build_prompt_with_context",
    "run_observe",
    "transition_tracker",
]

_PAGE_CONTEXT_JS = """() => ({
    scrollX: Math.round(window.scrollX),
    scrollY: Math.round(window.scrollY),
    viewportWidth: window.innerWidth,
    viewportHeight: window.innerHeight,
    pageWidth: document.documentElement.scrollWidth,
    pageHeight: document.documentElement.scrollHeight,
    url: window.location.href,
    title: document.title
})"""


def get_page_context(page: Page) -> str:
    """Gather scroll position, viewport, and page dimensions via page.evaluate().

    Returns a concise context string, or empty string on failure.
    """
    try:
        info = page.evaluate(_PAGE_CONTEXT_JS)
        scroll_y = info["scrollY"]
        page_height = info["pageHeight"]
        viewport_h = info["viewportHeight"]
        pct = round(scroll_y / max(page_height - viewport_h, 1) * 100) if page_height > viewport_h else 0

        return (
            f"[Page context] URL: {info['url']} | Title: {info['title']} | "
            f"Viewport: {info['viewportWidth']}x{viewport_h} | "
            f"Scroll: {scroll_y}px / {page_height}px tall ({pct}% scrolled)"
        )
    except (PlaywrightError, TypeError, KeyError):
        return ""


def build_prompt_with_context(prompt: str, page_context: str) -> str:
    """Prepend page context to a prompt if available."""
    if page_context:
        return f"{page_context}\n{prompt}"
    return prompt


def build_prompt_with_focus(base_prompt: str, focus: str | None) -> str:
    """Append focus instruction to a prompt if provided."""
    if focus:
        return f"{base_prompt} Focus specifically on: {focus}."
    return base_prompt


# ---------------------------------------------------------------------------
# Fast-path transition generation from snapshot diffs
# ---------------------------------------------------------------------------


def generate_fast_transition(
    before: list[SnapshotElement],
    after: list[SnapshotElement],
    action_description: str,
) -> str:
    """Generate a concise transition narrative from before/after snapshot diff.

    Compares element lists by (role, name) pairs to detect additions, removals,
    and value changes. Returns a human-readable summary.
    """
    before_map = {(e.role, e.name): e for e in before}
    after_map = {(e.role, e.name): e for e in after}

    before_keys = set(before_map)
    after_keys = set(after_map)

    added = after_keys - before_keys
    removed = before_keys - after_keys
    changed: list[str] = []
    for key in before_keys & after_keys:
        b, a = before_map[key], after_map[key]
        if b.value != a.value:
            changed.append(f"{key[0]} '{key[1]}' value changed")
        if b.checked != a.checked:
            changed.append(f"{key[0]} '{key[1]}' {'checked' if a.checked else 'unchecked'}")
        if b.disabled != a.disabled:
            changed.append(f"{key[0]} '{key[1]}' {'disabled' if a.disabled else 'enabled'}")

    parts = [action_description]
    if added:
        names = [f"{r} '{n}'" for r, n in sorted(added)[:5]]
        parts.append(f"New elements appeared: {', '.join(names)}")
    if removed:
        names = [f"{r} '{n}'" for r, n in sorted(removed)[:5]]
        parts.append(f"Elements removed: {', '.join(names)}")
    if changed:
        parts.append(f"Changes: {', '.join(changed[:5])}")
    if not added and not removed and not changed:
        parts.append("No visible changes detected.")

    return " ".join(parts)


def generate_structured_transition(
    before: list[SnapshotElement],
    after: list[SnapshotElement],
) -> dict[str, list[dict[str, object]]]:
    """Generate structured transition dict from before/after snapshot diff.

    Returns ``{appeared: [...], removed: [...], changed: [...]}``.
    Each sub-list is capped at 10 entries.
    """
    before_map = {(e.role, e.name): e for e in before}
    after_map = {(e.role, e.name): e for e in after}
    before_keys, after_keys = set(before_map), set(after_map)

    appeared: list[dict[str, object]] = [{"role": r, "name": n} for r, n in sorted(after_keys - before_keys)[:10]]
    removed: list[dict[str, object]] = [{"role": r, "name": n} for r, n in sorted(before_keys - after_keys)[:10]]

    changed: list[dict[str, object]] = []
    for key in sorted(before_keys & after_keys):
        b, a = before_map[key], after_map[key]
        if b.value != a.value:
            changed.append({"role": key[0], "name": key[1], "field": "value", "from": b.value, "to": a.value})
        if b.checked != a.checked:
            changed.append({"role": key[0], "name": key[1], "field": "checked", "from": b.checked, "to": a.checked})
        if b.disabled != a.disabled:
            changed.append({"role": key[0], "name": key[1], "field": "disabled", "from": b.disabled, "to": a.disabled})

    return {"appeared": appeared, "removed": removed, "changed": changed[:10]}


@dataclass
class TransitionTracker:
    """Captures before/after snapshots and generates transition narratives.

    Usage::

        tracker = TransitionTracker(page)
        tracker.capture_before()
        # ... perform action ...
        transition = tracker.transition("Clicked the button")
    """

    page: Page
    _before: list[SnapshotElement] = field(default_factory=list, init=False)

    def capture_before(self) -> None:
        """Capture the 'before' accessibility snapshot."""
        self._before = flatten_snapshot(self.page.accessibility.snapshot())

    def transition(self, description: str) -> str:
        """Capture 'after' snapshot and return transition narrative."""
        after = flatten_snapshot(self.page.accessibility.snapshot())
        return generate_fast_transition(self._before, after, description)


@contextmanager
def transition_tracker(page: Page) -> Iterator[TransitionTracker]:
    """Context manager that captures a before snapshot on entry.

    Usage::

        with transition_tracker(page) as tracker:
            # ... perform action ...
            result.transition = tracker.transition("Did something")
    """
    tracker = TransitionTracker(page)
    tracker.capture_before()
    yield tracker


# ---------------------------------------------------------------------------
# Observe — opt-in page layout description (separate act_get call)
# ---------------------------------------------------------------------------

OBSERVE_PROMPT = (
    "Without scrolling or clicking anything, describe the current visual layout "
    "of the page. Include: what content is visible, where key elements are "
    "positioned, colors and styling of major elements, and the general state of the page."
)


class ObserveSchema(BaseModel):
    layout: str


def run_observe(nova_act: NovaAct) -> str:
    """Fire a separate act_get() to describe the current page layout.

    Returns the layout string, or empty string on failure.
    """
    try:
        result = nova_act.act_get(OBSERVE_PROMPT, schema=ObserveSchema.model_json_schema())
        resp = result.parsed_response
        if isinstance(resp, dict):
            layout = resp.get("layout", "")
            return str(layout) if layout else ""
        return ""
    except RuntimeError:
        logger.debug("observe call failed", exc_info=True)
        return ""
