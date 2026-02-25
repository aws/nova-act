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
import json
from typing import Literal, TypedDict

from playwright.sync_api import Page

from nova_act.tools.browser.default.dom_actuation.click_events import get_after_click_events
from nova_act.tools.browser.default.util.bbox_parser import bounding_box_to_point
from nova_act.tools.browser.default.util.dispatch_dom_events import dispatch_event_sequence
from nova_act.tools.browser.default.util.element_helpers import (
    check_if_native_dropdown,
    get_element_at_point,
    recurse_through_iframes,
    viewport_dimensions,
)
from nova_act.tools.browser.default.util.file_upload_helpers import click_and_maybe_return_file_chooser
from nova_act.tools.browser.interface.types.agent_redirect_error import AgentRedirectError
from nova_act.tools.browser.interface.types.click_types import ClickOptions, ClickType
from nova_act.types.api.step import BboxTLBR
from nova_act.util.logging import setup_logging

_LOGGER = setup_logging(__name__)

NATIVE_DROPDOWN_REDIRECT_MESSAGE = (
    "This dropdown cannot be clicked. Use agentType(<value>, <same bbox>), with one of these values: "
)
FILE_UPLOAD_REDIRECT_MESSAGE = (
    "This file input cannot be clicked. Use agentType(<value>, <same bbox>), with this format: /path/to/file"
)


def agent_click(
    bbox: BboxTLBR,
    page: Page,
    click_type: ClickType = "left",
    click_options: ClickOptions | None = None,
) -> None:
    """
    Click at a point within a bounding box.

    Args:
        bounding_box: A dict representation of a bounding box
        page: Playwright Page object
        click_type: Type of click to perform. Options are:
                    "left" - single left click (default)
                    "left-double" - double left click
                    "right" - right click
    """
    bbox.validate_in_viewport(**viewport_dimensions(page))
    point = bounding_box_to_point(bbox)

    handle_special_elements(page, point["x"], point["y"])

    if check_if_native_dropdown(page, point["x"], point["y"]):
        dropdown_options = get_dropdown_options(page, point["x"], point["y"])
        error_message = NATIVE_DROPDOWN_REDIRECT_MESSAGE + json.dumps(
            dropdown_options, separators=(",", ":"), sort_keys=True
        )
        raise AgentRedirectError(error_message)

    if click_type == "left":
        # Do left click via this helper which will also let us know if there's a file upload chooser after our click
        # This is a work around to handle file uploads within cross-origin iframes,
        # where we can't use javascript to find file input elements
        chooser = click_and_maybe_return_file_chooser(page, x=point["x"], y=point["y"], timeout_ms=600)
        if chooser is not None:
            # The click has led to a file chooser. Redirect the agent
            raise AgentRedirectError(FILE_UPLOAD_REDIRECT_MESSAGE)
    elif click_type == "left-double":
        page.mouse.dblclick(point["x"], point["y"])
    elif click_type == "right":
        page.mouse.click(point["x"], point["y"], button="right")
    else:
        raise ValueError(f"Unknown click type: {click_type}")

    maybe_blur_field(page, point, click_options)


def maybe_blur_field(
    page: Page,
    point: dict[str, float],
    click_options: ClickOptions | None = None,
) -> None:
    if click_options is None or not click_options.get("blurField"):
        return

    after_click_events = get_after_click_events(point)
    dispatch_event_sequence(page, point, after_click_events)


class DropdownOption(TypedDict):
    """An option from a dropdown menu."""

    value: str
    label: str


def get_dropdown_options(page: Page, x: float, y: float) -> list[DropdownOption] | None:
    """Get options from a select element."""

    class _OptionsResult(TypedDict):
        """Typeguard for injected JS."""

        type_: Literal["options"]
        value: list[DropdownOption]

    result = recurse_through_iframes(
        page,
        x,
        y,
        """
        function shadowInclusiveParent(el) {
            if (!el) return null;
            if (el.parentElement) return el.parentElement;
            const root = el.getRootNode();
            if (root && root instanceof ShadowRoot) {
                return root.host || null;
            }
            return null;
        }

        function findNearestSelect(el) {
            let current = el;
            while (current) {
                if (current.tagName && current.tagName.toLowerCase() === "select") {
                    return current;
                }
                current = shadowInclusiveParent(current);
            }
            return null;
        }

        const selectElement = findNearestSelect(elem);
        if (!selectElement || !selectElement.options) return null;

        return {
            type_: 'options',
            value: Array.from(selectElement.options).map(option => ({
                value: option.label,
                label: option.label,
            }))
        };
        """,
        _OptionsResult,
    )

    if not isinstance(result, dict) or result.get("type_") != "options":
        _LOGGER.warning(f"Could not extract dropdown options from element at point {(x, y)}.")
        return None

    return result["value"]


def handle_special_elements(page: Page, x: float, y: float) -> None:
    element_info = get_element_at_point(page, x, y)
    if element_info is None:
        return

    # Check for special input types. Note that file uploads are handled by click_and_maybe_return_file_chooser
    if element_info["tagName"].lower() == "input":
        input_type = element_info.get("attributes", {}).get("type", "").lower()

        if input_type == "color":
            raise AgentRedirectError(
                "This color input cannot be clicked. Use agentType(<value>, <same bbox>), with this format: #RRGGBB"
            )
        elif input_type == "range":
            range_min = element_info.get("attributes", {}).get("min", "0")
            range_max = element_info.get("attributes", {}).get("max", "100")
            raise AgentRedirectError(
                f"This range input cannot be clicked. "
                f"Use agentType(<value>, <same bbox>), with a value from {range_min} to {range_max}."
            )
