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
"""Inspection capabilities — extract, get_content, screenshot, query_dom, get_styles, evaluate_js, diff."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from nova_act.cli.browser.services.action_results import DiffResult
from nova_act.cli.browser.utils.parsing import parse_json_schema

if TYPE_CHECKING:
    from playwright.sync_api import Locator

    from nova_act import NovaAct

# ---------------------------------------------------------------------------
# Pydantic schema models & constants
# ---------------------------------------------------------------------------
_DEFAULT_OBSERVE_PROMPT = "Describe what you observe on this page."


class _ObserveSchema(BaseModel):
    observation: str


DEFAULT_EVALUATE_TIMEOUT_SECONDS = 30

_GET_STYLES_JS = """
(args) => {
    const [selector, properties] = args;
    const elements = document.querySelectorAll(selector);
    if (elements.length === 0) return null;
    return Array.from(elements).map(el => {
        const computed = getComputedStyle(el);
        if (properties.length > 0) {
            const result = {};
            for (const prop of properties) {
                result[prop] = computed.getPropertyValue(prop);
            }
            return result;
        }
        const result = {};
        for (let i = 0; i < computed.length; i++) {
            const name = computed[i];
            result[name] = computed.getPropertyValue(name);
        }
        return result;
    });
}
"""

ALL_PROPERTIES = ("tag", "text", "visible", "boundingBox")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def wrap_with_timeout(expression: str, timeout_seconds: int) -> str:
    """Wrap a JS expression in Promise.race with a timeout."""
    timeout_ms = timeout_seconds * 1000
    escaped = expression.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
    return (
        f"Promise.race(["
        f"Promise.resolve().then(() => {{ return ({escaped}); }}),"
        f"new Promise((_, reject) => setTimeout("
        f"() => reject(new Error('Evaluation timed out after {timeout_seconds}s')), {timeout_ms}))"
        f"])"
    )


def is_complex_result(result: object) -> bool:
    return isinstance(result, (list, dict))


def _get_element_properties(element: "Locator", props: tuple[str, ...]) -> dict[str, object]:
    """Extract requested properties from a single element."""
    result: dict[str, object] = {}
    if "tag" in props:
        result["tag"] = element.evaluate("el => el.tagName.toLowerCase()")
    if "text" in props:
        result["text"] = element.inner_text()
    if "visible" in props:
        result["visible"] = element.is_visible()
    if "boundingBox" in props:
        result["boundingBox"] = element.bounding_box()
    return result


class InspectionMixin:
    """Inspection and extraction capabilities for BrowserActions."""

    _nova_act: NovaAct

    def extract(self, prompt: str, schema: str | None = None, timeout: int = 30, **method_args: object) -> object:
        """Extract structured data from the current page. Returns parsed response."""
        parsed_schema = parse_json_schema(schema)
        result = self._nova_act.act_get(
            prompt,
            schema=parsed_schema,  # type: ignore[arg-type]
            timeout=timeout,
            **method_args,  # type: ignore[arg-type]
        )
        return result.parsed_response if result.parsed_response is not None else result.response

    def get_content(self, output_format: str = "text") -> str:
        """Get page content in specified format (text, html, markdown)."""
        if output_format == "html":
            return self._nova_act.page.content()
        elif output_format == "markdown":
            from markdownify import markdownify as md

            return md(self._nova_act.page.content())
        else:
            return self._nova_act.page.inner_text("body")

    def screenshot(self, full_page: bool = False, output_format: str = "png", quality: int = 80) -> bytes:
        """Capture a screenshot. Returns raw bytes."""
        from nova_act.cli.browser.utils.browser_config_cli import (
            build_screenshot_kwargs,
        )

        screenshot_config = build_screenshot_kwargs(output_format, full_page, quality)
        return self._nova_act.page.screenshot(**screenshot_config.to_kwargs())  # type: ignore[arg-type]

    def query_dom(self, selector: str, properties: tuple[str, ...] = ALL_PROPERTIES) -> list[dict[str, object]]:
        """Query page elements matching a CSS selector and return their properties."""
        elements = self._nova_act.page.locator(selector).all()
        return [_get_element_properties(el, properties) for el in elements]

    def get_styles(self, selector: str, properties: tuple[str, ...] = ()) -> list[dict[str, object]]:
        """Get computed CSS styles for elements matching a selector.

        Raises if no elements found.
        """
        result = self._nova_act.page.evaluate(_GET_STYLES_JS, [selector, list(properties)])
        if result is None:
            raise ValueError(f"No elements found matching selector: {selector}")
        return result  # type: ignore[no-any-return]

    def evaluate_js(self, expression: str, timeout: int = DEFAULT_EVALUATE_TIMEOUT_SECONDS) -> object:
        """Evaluate a JavaScript expression in the page context.

        Raises on timeout (caller should handle).
        """
        wrapped = wrap_with_timeout(expression, timeout)
        return self._nova_act.page.evaluate(wrapped)

    def diff(
        self,
        action: str,
        observe: str | None = None,
        schema: str | None = None,
        focus: str | None = None,
        timeout: int = 30,
        **method_args: object,
    ) -> DiffResult:
        """Observe page state before and after an action using a single act_get call.

        Combines observation and action into one inference call for 3x cost/latency reduction.
        """
        obs_prompt = observe or _DEFAULT_OBSERVE_PROMPT
        focus_suffix = f" Focus on: {focus}." if focus else ""

        combined_prompt = (
            f"First, describe what you currently observe on the page ({obs_prompt}).{focus_suffix} "
            f"Then perform this action: {action}. "
            f"Then describe what you observe after the action ({obs_prompt}).{focus_suffix} "
            f"Return your observations as a JSON object with 'before' and 'after' keys."
        )

        combined_schema = {
            "type": "object",
            "properties": {
                "before": {"type": "object", "description": "Observation before the action"},
                "after": {"type": "object", "description": "Observation after the action"},
            },
            "required": ["before", "after"],
        }

        result = self._nova_act.act_get(
            combined_prompt,
            schema=combined_schema,  # type: ignore[arg-type]
            timeout=timeout,
            **method_args,  # type: ignore[arg-type]
        )
        data = result.parsed_response if result.parsed_response is not None else {}
        before = data.get("before", {}) if isinstance(data, dict) else {}
        after = data.get("after", {}) if isinstance(data, dict) else {}

        return DiffResult(action=action, observe=obs_prompt, before=before, after=after)
