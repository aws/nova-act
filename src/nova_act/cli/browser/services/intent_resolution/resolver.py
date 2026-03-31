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
"""Intent resolver: routes agent intent to fast (Playwright) or smart (AI) path."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from nova_act.cli.browser.services.intent_resolution.matching import (
    FUZZY_SCORE_THRESHOLD,
    detect_format,
    exact_match,
    token_set_match,
)
from nova_act.cli.browser.services.intent_resolution.snapshot import (
    SnapshotElement,
    flatten_snapshot,
)

if TYPE_CHECKING:
    from playwright.sync_api import Page


class ResolutionPath(Enum):
    FAST = "fast"
    SMART = "smart"


@dataclass
class ResolvedTarget:
    """Result of intent resolution."""

    path: ResolutionPath
    element: SnapshotElement | None = None
    confidence: float = 0.0
    match_method: str = ""


# Role filters per command type
CLICKABLE_ROLES = frozenset({"button", "link", "menuitem", "tab", "checkbox", "radio", "option", "switch", "treeitem"})
FILLABLE_ROLES = frozenset({"textbox", "searchbox", "combobox", "spinbutton", "textarea"})
SEARCH_ROLES = frozenset({"searchbox", "textbox", "button"})
HEADING_LANDMARK_ROLES = frozenset(
    {"heading", "region", "navigation", "contentinfo", "banner", "main", "complementary"}
)

HEADING_LANDMARK_BONUS = 5


def _filter_by_command(elements: list[SnapshotElement], command_type: str) -> list[SnapshotElement]:
    """Filter elements by roles relevant to the command type."""
    if command_type == "click":
        return [e for e in elements if e.role in CLICKABLE_ROLES]
    if command_type == "fill-form":
        return [e for e in elements if e.role in FILLABLE_ROLES]
    if command_type == "search":
        return [e for e in elements if e.role in SEARCH_ROLES or "search" in (e.name or "").lower()]
    # scroll-to: all elements (bonus applied in matching)
    return elements


def resolve(target: str, command_type: str, page: "Page") -> ResolvedTarget:
    """Resolve agent intent to a fast or smart path.

    Args:
        target: Natural language target, CSS selector, or snapshot ref.
        command_type: One of "click", "fill-form", "scroll-to", "search".
        page: Playwright Page for accessibility snapshot.

    Returns:
        ResolvedTarget indicating which path to take.
    """
    # Tier 1: Format detection (no snapshot needed)
    fmt = detect_format(target)
    if fmt:
        if fmt.kind == "snapshot_ref":
            # Need snapshot to look up the ref
            tree = page.accessibility.snapshot()
            elements = flatten_snapshot(tree)
            for elem in elements:
                if elem.ref.lower() == fmt.value.lower():
                    return ResolvedTarget(path=ResolutionPath.FAST, element=elem, confidence=100.0, match_method="ref")
            return ResolvedTarget(path=ResolutionPath.SMART, match_method="ref_not_found")
        # CSS selector — fast path directly
        return ResolvedTarget(path=ResolutionPath.FAST, confidence=100.0, match_method="selector")

    # Tier 2 & 3: Need snapshot
    tree = page.accessibility.snapshot()
    elements = flatten_snapshot(tree)
    filtered = _filter_by_command(elements, command_type)

    # Tier 2: Exact match
    exact = exact_match(target, filtered)
    if exact:
        return ResolvedTarget(path=ResolutionPath.FAST, element=exact, confidence=100.0, match_method="exact")

    # Tier 3: Token set ratio
    result = token_set_match(target, filtered)

    # Apply heading/landmark bonus for scroll-to
    if command_type == "scroll-to" and result.element and not result.confident:
        if result.element.role in HEADING_LANDMARK_ROLES:
            boosted = result.score + HEADING_LANDMARK_BONUS
            if boosted >= FUZZY_SCORE_THRESHOLD:
                # Re-check with bonus — need to verify gap still holds
                result_confident = result.score >= (FUZZY_SCORE_THRESHOLD - HEADING_LANDMARK_BONUS)
                if result_confident:
                    return ResolvedTarget(
                        path=ResolutionPath.FAST,
                        element=result.element,
                        confidence=boosted,
                        match_method="token_set_ratio_boosted",
                    )

    if result.confident and result.element:
        return ResolvedTarget(
            path=ResolutionPath.FAST, element=result.element, confidence=result.score, match_method="token_set_ratio"
        )

    return ResolvedTarget(path=ResolutionPath.SMART, match_method="no_match")
