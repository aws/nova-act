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
"""Interaction capabilities — execute, ask, fill_form, verify, wait_for."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING
from urllib.parse import urldefrag

from playwright.sync_api import Error as PlaywrightError
from pydantic import BaseModel

from nova_act.cli.browser.services.action_results import (
    AskResult,
    ClickResult,
    ExecuteResult,
    FillFormResult,
    TypeResult,
    VerifyResult,
    WaitForResult,
)
from nova_act.cli.browser.services.browser_actions.utils import (
    BOOL_SCHEMA,
    build_prompt_with_context,
    build_prompt_with_focus,
    get_page_context,
    transition_tracker,
)
from nova_act.cli.browser.services.intent_resolution import ResolutionPath, resolve
from nova_act.cli.browser.services.intent_resolution.resolver import FILLABLE_ROLES
from nova_act.cli.browser.utils.parsing import parse_json_schema

if TYPE_CHECKING:
    from nova_act import NovaAct

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic schema models
# ---------------------------------------------------------------------------
class _AskDefaultSchema(BaseModel):
    answer: str


class _FillFormSchema(BaseModel):
    outcome: str


class _VerifySchema(BaseModel):
    passed: bool
    actual: str
    evidence: str


class _ClickSchema(BaseModel):
    clicked: bool


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------
_ASK_PROMPT = (
    "Answer the following question based on what is visible on the page. "
    "You MAY scroll up or down to find the answer. "
    "Do NOT click links, navigate to other pages, type, or submit forms. "
    "Question: {question}"
)

_FILL_FORM_NO_SUBMIT = (
    "Fill in the form on this page with the following information: {form_data}. " "Do NOT submit the form."
)
_FILL_FORM_SUBMIT = (
    "Fill in the form on this page with the following information: {form_data}. " "Then submit the form."
)

_VERIFY_ASSERTION_PROMPT = (
    "Determine if the following is true on this page: {assertion}. "
    "You may scroll, expand sections, or interact with the page as needed to check. "
    "Report: whether it passed (true/false), what you actually see, and your evidence."
)

_POLL_PROMPT = "Is the following condition currently met on this page: {condition}? Answer true or false."

_CLICK_PROMPT = "Click on the following element: {target}."


def _urls_differ_ignoring_fragment(url_before: str, url_after: str) -> bool:
    """Return True if URLs differ ignoring fragment (anchor) portion."""
    return urldefrag(url_before).url != urldefrag(url_after).url


class InteractionMixin:
    """Interaction capabilities for BrowserActions."""

    _nova_act: NovaAct

    def execute(self, prompt: str, timeout: int, **method_args: object) -> ExecuteResult:
        """Execute a browser action via act(). Returns an ExecuteResult with transition."""
        with transition_tracker(self._nova_act.page) as tracker:
            page_ctx = get_page_context(self._nova_act.page)
            self._nova_act.act(
                build_prompt_with_context(prompt, page_ctx),
                timeout=timeout,
                **method_args,  # type: ignore[arg-type]
            )
            return ExecuteResult(transition=tracker.transition(f"Executed: {prompt[:80]}"))

    def _try_fast_click(self, target: str) -> ClickResult | None:
        """Attempt fast-path click via intent resolution. Returns ClickResult on success, None on failure."""
        try:
            resolved = resolve(target, "click", self._nova_act.page)
            if resolved.path != ResolutionPath.FAST:
                return None
            with transition_tracker(self._nova_act.page) as tracker:
                if resolved.match_method == "selector":
                    self._nova_act.page.locator(target).first.click()
                elif resolved.element is not None:
                    self._nova_act.page.get_by_role(
                        resolved.element.role, name=resolved.element.name  # type: ignore[arg-type]
                    ).click()
                else:
                    return None
                return ClickResult(clicked=target, transition=tracker.transition(f"Clicked '{target}' via fast path."))
        except PlaywrightError:
            logger.debug("Fast click failed for '%s', falling back to AI", target)
            return None

    def click(self, target: str, focus: str | None = None, timeout: int = 30, **method_args: object) -> ClickResult:
        """Click a specific element. Tries fast path (Playwright) first, falls back to AI."""
        # --- Fast path: intent resolution → Playwright click ---
        fast_result = self._try_fast_click(target)
        if fast_result is not None:
            return fast_result

        # --- Smart path: AI act_get ---
        with transition_tracker(self._nova_act.page) as tracker:
            prompt = build_prompt_with_focus(_CLICK_PROMPT.format(target=target), focus)
            result = self._nova_act.act_get(
                prompt,
                schema=_ClickSchema.model_json_schema(),
                timeout=timeout,
                **method_args,  # type: ignore[arg-type]
            )
            data = result.parsed_response if result.parsed_response is not None else {}
            return ClickResult(
                clicked=target if (isinstance(data, dict) and data.get("clicked", False)) else "",
                transition=tracker.transition(f"Clicked '{target}'."),
            )

    def ask(
        self,
        question: str,
        schema: str | None = None,
        focus: str | None = None,
        timeout: int = 30,
        **method_args: object,
    ) -> AskResult:
        """Ask a read-only question about the current page.

        Allows scrolling but validates that the page URL did not change
        (navigation is forbidden).
        """
        url_before = self._nova_act.page.url
        prompt = build_prompt_with_focus(_ASK_PROMPT.format(question=question), focus)
        act_schema = parse_json_schema(schema) if schema else _AskDefaultSchema.model_json_schema()
        result = self._nova_act.act_get(
            prompt,
            schema=act_schema,  # type: ignore[arg-type]
            timeout=timeout,
            **method_args,  # type: ignore[arg-type]
        )
        answer = result.parsed_response if result.parsed_response is not None else {}
        answer_value = answer.get("answer", "") if isinstance(answer, dict) and not schema else answer

        # Post-action URL validation: detect if the model navigated away
        url_after = self._nova_act.page.url
        url_changed = _urls_differ_ignoring_fragment(url_before, url_after)

        return AskResult(question=question, answer=answer_value, url_changed=url_changed)

    def _try_fast_fill(self, fields: dict[str, str]) -> tuple[dict[str, str], str]:
        """Attempt fast-path fill for each field independently. Returns (failed_fields, transition)."""
        failed: dict[str, str] = {}
        filled_count = 0
        with transition_tracker(self._nova_act.page) as tracker:
            for key, value in fields.items():
                try:
                    resolved = resolve(key, "fill-form", self._nova_act.page)
                    if resolved.path != ResolutionPath.FAST or resolved.element is None:
                        failed[key] = value
                        continue
                    self._nova_act.page.get_by_role(
                        resolved.element.role, name=resolved.element.name  # type: ignore[arg-type]
                    ).fill(value)
                    filled_count += 1
                except PlaywrightError:
                    logger.debug("Fast fill failed for field '%s', deferring to AI", key)
                    failed[key] = value
            return failed, tracker.transition(f"Filled {filled_count} field(s) via fast path.")

    def fill_form(
        self,
        form_data: dict[str, str],
        submit: bool = False,
        focus: str | None = None,
        timeout: int = 30,
        **method_args: object,
    ) -> FillFormResult:
        """Fill out a form on the current page using per-field resolution.

        Tries Playwright fill for each field independently, then passes only
        unmatched fields to AI as a reduced JSON.
        """
        import json as _json

        instruction = _json.dumps(form_data)

        # --- Fast path: per-field resolution ---
        failed_fields, transition = self._try_fast_fill(form_data)

        if not failed_fields:
            # All fields filled via Playwright
            if submit:
                # Still need AI to submit since we don't know which button/action submits
                with transition_tracker(self._nova_act.page) as tracker:
                    self._nova_act.act_get(
                        build_prompt_with_focus("Submit the form on this page.", focus),
                        schema=_FillFormSchema.model_json_schema(),
                        timeout=timeout,
                        **method_args,  # type: ignore[arg-type]
                    )
                    transition = tracker.transition("Submitted the form.")
            return FillFormResult(
                instruction=instruction,
                submitted=submit,
                outcome="All fields filled via fast path.",
                transition=transition,
            )

        # --- Smart path: AI fills only the failed fields ---
        ai_data = _json.dumps(failed_fields)
        template = _FILL_FORM_SUBMIT if submit else _FILL_FORM_NO_SUBMIT
        with transition_tracker(self._nova_act.page) as tracker:
            prompt = build_prompt_with_focus(template.format(form_data=ai_data), focus)
            result = self._nova_act.act_get(
                prompt,
                schema=_FillFormSchema.model_json_schema(),
                timeout=timeout,
                **method_args,  # type: ignore[arg-type]
            )
            data = result.parsed_response if result.parsed_response is not None else {}
            fast_count = len(form_data) - len(failed_fields)
            ai_outcome = str(data.get("outcome", "")) if isinstance(data, dict) else str(data)
            outcome = f"{fast_count} field(s) filled via fast path. {ai_outcome}" if fast_count > 0 else ai_outcome
            return FillFormResult(
                instruction=instruction,
                submitted=submit,
                outcome=outcome,
                transition=tracker.transition("Filled form fields via AI."),
            )

    def verify(
        self, assertion: str, focus: str | None = None, timeout: int = 30, **method_args: object
    ) -> VerifyResult:
        """Visually assert a condition on the current page."""
        with transition_tracker(self._nova_act.page) as tracker:
            prompt = build_prompt_with_focus(_VERIFY_ASSERTION_PROMPT.format(assertion=assertion), focus)
            page_ctx = get_page_context(self._nova_act.page)
            result = self._nova_act.act_get(
                build_prompt_with_context(prompt, page_ctx),
                schema=_VerifySchema.model_json_schema(),
                timeout=timeout,
                **method_args,  # type: ignore[arg-type]
            )
            data = result.parsed_response if result.parsed_response is not None else {}
            return VerifyResult(
                passed=bool(data.get("passed", False)) if isinstance(data, dict) else False,
                actual=str(data.get("actual", "")) if isinstance(data, dict) else str(data),
                evidence=str(data.get("evidence", "")) if isinstance(data, dict) else "",
                transition=tracker.transition(f"Verified: {assertion[:80]}"),
            )

    def wait_for(
        self,
        condition: str,
        timeout: int = 30,
        interval: int = 5,
        focus: str | None = None,
        per_call_timeout: int = 30,
        **method_args: object,
    ) -> WaitForResult:
        """Poll until a condition is met on the current page."""
        prompt = build_prompt_with_focus(_POLL_PROMPT.format(condition=condition), focus)
        with transition_tracker(self._nova_act.page) as tracker:
            start = time.monotonic()
            polls = 0
            met = False

            while True:
                elapsed = time.monotonic() - start
                remaining = timeout - elapsed
                if remaining <= 0:
                    break

                polls += 1
                call_timeout = int(min(remaining, per_call_timeout))
                try:
                    result = self._nova_act.act_get(
                        prompt,
                        schema=BOOL_SCHEMA,
                        timeout=call_timeout,
                        **method_args,  # type: ignore[arg-type]
                    )

                    if result.parsed_response is True:
                        met = True
                        break
                except RuntimeError as e:
                    logger.debug("Wait-for poll %d failed for '%s': %s", polls, condition, e)
                    break

                remaining_after = timeout - (time.monotonic() - start)
                if remaining_after <= 0:
                    break
                time.sleep(min(interval, remaining_after))

            return WaitForResult(
                met=met,
                elapsed_seconds=round(time.monotonic() - start, 1),
                polls=polls,
                transition=tracker.transition(f"The condition '{condition}' was {'met' if met else 'not met'}."),
            )

    def type_text(
        self,
        text: str,
        target: str | None = None,
        append: bool = False,
        timeout: int = 30,
        **method_args: object,
    ) -> TypeResult:
        """Type text into a target element or the currently focused element.

        Fast path: resolve target via intent resolution → Playwright fill/type.
        AI fallback: act() with natural language prompt.
        """
        # Fast path: type into focused element
        if target is None:
            try:
                focused = self._nova_act.page.locator(":focus")
                if focused.count() > 0:
                    with transition_tracker(self._nova_act.page) as tracker:
                        if append:
                            focused.type(text)
                        else:
                            focused.fill(text)
                        return TypeResult(
                            typed=text,
                            target="focused element",
                            transition=tracker.transition(f"Typed '{text}' into focused element"),
                        )
            except PlaywrightError:
                logger.debug("Fast-path type into focused element failed")

        # Fast path: resolve target
        if target:
            try:
                resolution = resolve(target, "fill-form", self._nova_act.page)
                if resolution.path == ResolutionPath.FAST and resolution.element:
                    if resolution.element.role not in FILLABLE_ROLES:
                        logger.debug(
                            "Fast-path target '%s' has non-fillable role '%s', falling back to AI",
                            target,
                            resolution.element.role,
                        )
                    else:
                        with transition_tracker(self._nova_act.page) as tracker:
                            locator = self._nova_act.page.get_by_role(
                                resolution.element.role, name=resolution.element.name  # type: ignore[arg-type]
                            )
                            if append:
                                locator.type(text)
                            else:
                                locator.fill(text)
                            return TypeResult(
                                typed=text,
                                target=target,
                                transition=tracker.transition(f"Typed '{text}' into '{target}'"),
                            )
            except PlaywrightError:
                logger.debug("Fast-path type into target '%s' failed, falling back to AI", target)

        # AI fallback
        target_desc = target or "the currently focused input field"
        prompt = f"Type the following text into {target_desc}: {text}"
        self._nova_act.act(prompt, timeout=timeout, **method_args)  # type: ignore[arg-type]
        return TypeResult(typed=text, target=target_desc, transition=f"Typed '{text}' into '{target_desc}'")
