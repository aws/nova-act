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
"""Navigation capabilities — goto and navigate with verification."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from nova_act.cli.browser.services.action_results import NavigateResult, ScrollToResult
from nova_act.cli.browser.services.browser_actions.utils import (
    BOOL_SCHEMA,
    build_prompt_with_context,
    build_prompt_with_focus,
    get_page_context,
    transition_tracker,
)
from nova_act.cli.browser.services.intent_resolution import ResolutionPath, resolve
from nova_act.cli.browser.utils.timeout import temporary_navigation_timeout

if TYPE_CHECKING:
    from nova_act import NovaAct

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------
_NAV_PROMPT = "{instruction}"
_VERIFY_PROMPT = (
    "I just asked the browser to: {instruction}. "
    "Look at the current page and determine if the action was successful — "
    "did the page change as expected? "
    "Answer true if yes, false if not."
)

_SCROLL_PROMPT = (
    "Scroll the page to find: {target}. " "Only scroll — do NOT click links, navigate, type, or submit forms."
)
_SCROLL_VERIFY_PROMPT = (
    "Is the following content currently visible on the page: {target}? " "Answer true if yes, false if not."
)


class NavigationMixin:
    """Navigation capabilities for BrowserActions."""

    _nova_act: NovaAct

    def goto(self, url: str, timeout: int | None = None) -> None:
        """Navigate to a URL via raw Playwright go_to_url."""
        with temporary_navigation_timeout(self._nova_act, timeout):
            self._nova_act.go_to_url(url)

    def navigate(
        self,
        instruction: str,
        focus: str | None = None,
        max_retries: int = 3,
        timeout: int = 30,
        **method_args: object,
    ) -> NavigateResult:
        """Execute a natural-language navigation instruction with verification retry loop."""
        nav_prompt = build_prompt_with_focus(_NAV_PROMPT.format(instruction=instruction), focus)
        verify_prompt = build_prompt_with_focus(_VERIFY_PROMPT.format(instruction=instruction), focus)

        with transition_tracker(self._nova_act.page) as tracker:
            page_ctx = get_page_context(self._nova_act.page)
            self._nova_act.act(
                build_prompt_with_context(nav_prompt, page_ctx),
                timeout=timeout,
                **method_args,  # type: ignore[arg-type]
            )

            arrived = False
            attempts = 0
            for _ in range(1, max_retries + 1):
                attempts += 1
                page_ctx = get_page_context(self._nova_act.page)
                result = self._nova_act.act_get(
                    build_prompt_with_context(verify_prompt, page_ctx),
                    schema=BOOL_SCHEMA,
                    timeout=timeout,
                    **method_args,  # type: ignore[arg-type]
                )
                if result.parsed_response is True:
                    arrived = True
                    break

            return NavigateResult(
                arrived=arrived,
                current_page=self._nova_act.page.url,
                attempts=attempts,
                transition=tracker.transition(f"Navigation to '{instruction}' {'succeeded' if arrived else 'failed'}."),
            )

    def _try_fast_scroll(self, target: str) -> str | None:
        """Attempt fast-path scroll via intent resolution. Returns transition string on success, None on failure."""
        try:
            resolved = resolve(target, "scroll-to", self._nova_act.page)
            if resolved.path != ResolutionPath.FAST:
                return None
            with transition_tracker(self._nova_act.page) as tracker:
                if resolved.match_method == "selector":
                    self._nova_act.page.locator(target).first.scroll_into_view_if_needed()
                elif resolved.element is not None:
                    self._nova_act.page.get_by_role(
                        resolved.element.role, name=resolved.element.name  # type: ignore[arg-type]
                    ).scroll_into_view_if_needed()
                else:
                    return None
                return tracker.transition(f"Scrolled to '{target}' via fast path.")
        except Exception:
            logger.debug("Fast scroll failed for '%s', falling back to AI loop", target)
            return None

    def scroll_to(
        self,
        target: str,
        max_attempts: int = 5,
        timeout: int = 30,
        **method_args: object,
    ) -> ScrollToResult:
        """Scroll to target content. Tries fast path (Playwright) first, falls back to AI loop."""
        # --- Fast path: intent resolution → Playwright scroll ---
        fast_transition = self._try_fast_scroll(target)
        if fast_transition is not None:
            return ScrollToResult(reached=True, target=target, attempts=0, transition=fast_transition)

        # --- Smart path: AI scroll + verify loop ---
        scroll_prompt = _SCROLL_PROMPT.format(target=target)
        verify_prompt = _SCROLL_VERIFY_PROMPT.format(target=target)

        with transition_tracker(self._nova_act.page) as tracker:
            reached = False
            final_attempt = max_attempts
            for attempt in range(1, max_attempts + 1):
                try:
                    page_ctx = get_page_context(self._nova_act.page)
                    self._nova_act.act(
                        build_prompt_with_context(scroll_prompt, page_ctx),
                        timeout=timeout,
                        **method_args,  # type: ignore[arg-type]
                    )

                    page_ctx = get_page_context(self._nova_act.page)
                    result = self._nova_act.act_get(
                        build_prompt_with_context(verify_prompt, page_ctx),
                        schema=BOOL_SCHEMA,
                        timeout=timeout,
                        **method_args,  # type: ignore[arg-type]
                    )
                    if result.parsed_response is True:
                        reached = True
                        final_attempt = attempt
                        break
                except RuntimeError as e:
                    logger.debug("Scroll attempt %d failed for '%s': %s", attempt, target, e)
                    final_attempt = attempt
                    break

            return ScrollToResult(
                reached=reached,
                target=target,
                attempts=final_attempt,
                transition=tracker.transition(f"Scroll to '{target}' {'reached' if reached else 'not found'}."),
            )
