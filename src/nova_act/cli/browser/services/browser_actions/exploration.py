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
"""Exploration capabilities — explore and search."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel, JsonValue

from nova_act.cli.browser.services.action_results import ExploreResult, SearchResult
from nova_act.cli.browser.services.browser_actions.utils import (
    build_prompt_with_context,
    build_prompt_with_focus,
    get_page_context,
    transition_tracker,
)
from nova_act.cli.browser.services.intent_resolution import (
    SnapshotElement,
    flatten_snapshot,
)

if TYPE_CHECKING:
    from nova_act import NovaAct

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic schema models
# ---------------------------------------------------------------------------
class _ExploreSchema(BaseModel):
    page_summary: str
    interactive_elements: list[str]
    current_state: str


class _StepSchema(BaseModel):
    findings: str
    new_elements: list[str]


class _SearchSchema(BaseModel):
    found: bool
    location: str
    summary: str


_INITIAL_PROMPT = (
    "Describe what you see on this page: main content summary, "
    "interactive elements (buttons, links, forms, inputs), and current page state. "
    "Identify areas worth exploring further. Be concise."
)
_FOCUSED_EXPLORE_PROMPTS = [
    (
        "Scroll down and look for more content related to: {focus}. "
        "Click into any relevant sections or links about {focus}."
    ),
    (
        "Continue exploring — look for additional details, sub-pages, or hidden content about: {focus}. "
        "Expand any collapsed sections."
    ),
    (
        "Dig deeper — follow any remaining links or navigation related to: {focus}. "
        "Check sidebars, footers, or secondary menus."
    ),
]
_BROAD_EXPLORE_PROMPTS = [
    (
        "Scroll down to see more content on this page. "
        "Click into the most important section or link you haven't explored yet."
    ),
    (
        "Continue exploring — navigate to another major section of this site. "
        "Check the main navigation menu for unvisited areas."
    ),
    ("Dig deeper — explore any remaining important sections, sub-pages, " "or content areas you haven't covered yet."),
]
_FOCUSED_OBSERVE_PROMPT = (
    "Describe what you now see after exploring. "
    "What new content or information about {focus} did you find? "
    "What interactive elements are visible now?"
)
_BROAD_OBSERVE_PROMPT = (
    "Describe what you now see after exploring. "
    "What new content or information did you find? "
    "What interactive elements are visible now?"
)

_SEARCH_PROMPT = (
    "Find the following on this website: {query}. "
    "Use site search, navigation menus, or page scanning — whatever works best. "
    "Report whether you found it, where it is, and a brief summary."
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_focused_prompt(step: int, focus: str) -> str:
    """Build the act() prompt for a focused exploration step."""
    idx = min(step - 2, len(_FOCUSED_EXPLORE_PROMPTS) - 1)
    return _FOCUSED_EXPLORE_PROMPTS[idx].format(focus=focus)


def _build_broad_prompt(step: int) -> str:
    """Build the act() prompt for a broad exploration step."""
    idx = min(step - 2, len(_BROAD_EXPLORE_PROMPTS) - 1)
    return _BROAD_EXPLORE_PROMPTS[idx]


def _build_explore_prompt(step: int, focus: str | None) -> str:
    """Build the act() prompt for an exploration step.

    Delegates to _build_focused_prompt or _build_broad_prompt based on focus.
    """
    if focus:
        return _build_focused_prompt(step, focus)
    return _build_broad_prompt(step)


def _build_observe_prompt(focus: str | None) -> str:
    """Build the act_get() prompt for observing after exploration."""
    if focus:
        return _FOCUSED_OBSERVE_PROMPT.format(focus=focus)
    return _BROAD_OBSERVE_PROMPT


def _aggregate_findings(
    initial_data: dict[str, JsonValue],
    step_results: list[dict[str, JsonValue]],
    depth: int,
) -> ExploreResult:
    """Merge initial overview with findings from exploration steps."""
    raw_elements = initial_data.get("interactive_elements", [])
    all_elements: list[str] = [str(e) for e in raw_elements] if isinstance(raw_elements, list) else []
    summaries: list[str] = [str(initial_data.get("page_summary", ""))]

    for step_data in step_results:
        summaries.append(str(step_data.get("findings", "")))
        new_elements = step_data.get("new_elements", [])
        if isinstance(new_elements, list):
            all_elements.extend(str(e) for e in new_elements)

    unique_elements = list(dict.fromkeys(all_elements))
    sections = [s for s in summaries if s]

    return ExploreResult(
        page_summary=" | ".join(s for s in summaries if s),
        interactive_elements=unique_elements,
        current_state=str(initial_data.get("current_state", "")),
        sections_explored=sections,
        exploration_depth=depth,
    )


class ExplorationMixin:
    """Exploration and search capabilities for BrowserActions."""

    _nova_act: NovaAct

    def explore(
        self, focus: str | None = None, depth: int = 3, timeout: int = 30, **method_args: object
    ) -> ExploreResult:
        """Multi-step structured exploration of the current page."""
        initial_prompt = build_prompt_with_focus(_INITIAL_PROMPT, focus)

        page_ctx = get_page_context(self._nova_act.page)
        initial_result = self._nova_act.act_get(
            build_prompt_with_context(initial_prompt, page_ctx),
            schema=_ExploreSchema.model_json_schema(),
            timeout=timeout,
            **method_args,  # type: ignore[arg-type]
        )
        initial_data = initial_result.parsed_response if isinstance(initial_result.parsed_response, dict) else {}

        step_results: list[dict[str, JsonValue]] = []
        for step in range(2, depth + 1):
            explore_prompt = _build_explore_prompt(step, focus)
            page_ctx = get_page_context(self._nova_act.page)
            self._nova_act.act(
                build_prompt_with_context(explore_prompt, page_ctx),
                timeout=timeout,
                **method_args,  # type: ignore[arg-type]
            )

            observe_prompt = _build_observe_prompt(focus)
            page_ctx = get_page_context(self._nova_act.page)
            step_result = self._nova_act.act_get(
                build_prompt_with_context(observe_prompt, page_ctx),
                schema=_StepSchema.model_json_schema(),
                timeout=timeout,
                **method_args,  # type: ignore[arg-type]
            )
            step_data = step_result.parsed_response if isinstance(step_result.parsed_response, dict) else {}
            step_results.append(step_data)

        return _aggregate_findings(initial_data, step_results, depth)

    def _find_search_element(self) -> SnapshotElement | None:
        """Find a search input element from the accessibility snapshot.

        Looks for: searchbox (any), textbox with "search" in name, button with "search" in name.
        Returns the best match by priority: searchbox > textbox > button.
        """
        try:
            tree = self._nova_act.page.accessibility.snapshot()
            elements = flatten_snapshot(tree)
        except Exception:
            return None

        best: SnapshotElement | None = None
        best_priority = 4  # lower is better
        for elem in elements:
            if elem.role == "searchbox":
                return elem  # highest priority — return immediately
            if elem.role == "textbox" and "search" in elem.name.lower() and best_priority > 2:
                best, best_priority = elem, 2
            elif elem.role == "button" and "search" in elem.name.lower() and best_priority > 3:
                best, best_priority = elem, 3
        return best

    def _try_fast_search(self, query: str) -> SearchResult | None:
        """Attempt fast-path search via snapshot element detection. Returns SearchResult on success, None on failure."""
        try:
            elem = self._find_search_element()
            if elem is None:
                return None

            page = self._nova_act.page
            with transition_tracker(page) as tracker:
                if elem.role in ("searchbox", "textbox"):
                    page.get_by_role(elem.role, name=elem.name).fill(query)  # type: ignore[arg-type]
                    page.keyboard.press("Enter")
                    return SearchResult(
                        found=True,
                        location="search results",
                        summary=f"Searched for '{query}' via fast path.",
                        transition=tracker.transition(f"Typed '{query}' into search and submitted."),
                    )

                if elem.role == "button":
                    page.get_by_role("button", name=elem.name).click()
                    page.wait_for_timeout(500)
                    revealed = self._find_search_element()
                    if revealed and revealed.role in ("searchbox", "textbox"):
                        page.get_by_role(revealed.role, name=revealed.name).fill(query)  # type: ignore[arg-type]
                        page.keyboard.press("Enter")
                        return SearchResult(
                            found=True,
                            location="search results",
                            summary=f"Searched for '{query}' via fast path (search icon).",
                            transition=tracker.transition(f"Clicked search icon, typed '{query}', and submitted."),
                        )
                    return None

        except Exception:
            logger.debug("Fast search failed for '%s', falling back to AI", query)
            return None
        return None

    def search(self, query: str, focus: str | None = None, timeout: int = 30, **method_args: object) -> SearchResult:
        """Search the current website for content. Tries fast path first, falls back to AI."""
        # --- Fast path: find search input via snapshot ---
        fast_result = self._try_fast_search(query)
        if fast_result is not None:
            return fast_result

        # --- Smart path: AI search ---
        with transition_tracker(self._nova_act.page) as tracker:
            prompt = build_prompt_with_focus(_SEARCH_PROMPT.format(query=query), focus)
            result = self._nova_act.act_get(
                prompt,
                schema=_SearchSchema.model_json_schema(),
                timeout=timeout,
                **method_args,  # type: ignore[arg-type]
            )
            data = result.parsed_response if isinstance(result.parsed_response, dict) else {}
            return SearchResult(
                found=bool(data.get("found", False)),
                location=str(data.get("location", "")),
                summary=str(data.get("summary", "")),
                transition=tracker.transition(f"Searched for '{query}'."),
            )
