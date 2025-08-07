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
from typing import Any, Dict, Literal, Optional

from playwright.sync_api import Page

from nova_act.impl.custom_actuation.interface.types.agent_redirect_error import AgentRedirectError
from nova_act.impl.custom_actuation.interface.types.click_options import ClickOptions
from nova_act.impl.custom_actuation.playwright.dom_actuation.click_events import get_after_click_events
from nova_act.impl.custom_actuation.playwright.util.bbox_parser import bounding_box_to_point, parse_bbox_string
from nova_act.impl.custom_actuation.playwright.util.dispatch_dom_events import dispatch_event_sequence
from nova_act.impl.custom_actuation.playwright.util.element_helpers import (
    check_if_native_dropdown,
    get_element_at_point,
    locate_element,
)

NATIVE_DROPDOWN_REDIRECT_MESSAGE = (
    "This dropdown cannot be clicked. Use agentType(<value>, <same bbox>), with one of these values: "
)


def agent_click(
    bounding_box: str,
    page: Page,
    click_type: Literal["left", "left-double", "right"] = "left",
    click_options: Optional[ClickOptions] = None,
) -> None:
    """
    Click at a point within a bounding box.

    Args:
        bounding_box: String representation of the bounding box
        page: Playwright Page object
        click_type: Type of click to perform. Options are:
                    "left" - single left click (default)
                    "left-double" - double left click
                    "right" - right click
    """
    bbox_dict = parse_bbox_string(bounding_box)
    point = bounding_box_to_point(bbox_dict)

    handle_special_elements(page, point["x"], point["y"])

    if check_if_native_dropdown(page, point["x"], point["y"]):
        dropdown_options = get_dropdown_options(page, point["x"], point["y"])
        error_message = NATIVE_DROPDOWN_REDIRECT_MESSAGE + json.dumps(
            dropdown_options, separators=(",", ":"), sort_keys=True
        )
        raise AgentRedirectError(error_message)

    if click_type == "left":
        page.mouse.click(point["x"], point["y"])
    elif click_type == "left-double":
        page.mouse.dblclick(point["x"], point["y"])
    elif click_type == "right":
        page.mouse.click(point["x"], point["y"], button="right")

    maybe_blur_field(page, point, click_options)


def maybe_blur_field(
    page: Page,
    point: Dict[str, float],
    click_options: Optional[ClickOptions] = None,
) -> None:
    if click_options is None or not click_options.get("blurField"):
        return

    element_info = get_element_at_point(page, point["x"], point["y"])
    if element_info is None:
        return

    element = locate_element(element_info, page)

    after_click_events = get_after_click_events(point)

    dispatch_event_sequence(element, after_click_events)


def get_dropdown_options(page: Page, x: float, y: float) -> Any | None:
    """Get options from a select element."""

    # Use evaluate to extract options
    options = page.evaluate(
        """
        ([x, y]) => {
            const elem = document.elementFromPoint(x, y);
            if (!elem) return null;
            if (!elem.options) return null;
            return Array.from(elem.options).map(option => ({
                value: option.label,
            }));
        }
    """,
        [x, y],
    )

    return options


def handle_special_elements(page: Page, x: float, y: float) -> None:
    element_info = get_element_at_point(page, x, y)
    if element_info is None:
        return

    # Check for color input, file input, or range input.
    # If any of the input above, raise AgentRedirectError
    if element_info["tagName"].lower() == "input":
        input_type = element_info.get("attributes", {}).get("type", "").lower()

        if input_type == "color":
            raise AgentRedirectError(
                "This color input cannot be clicked. Use agentType(<value>, <same bbox>), with this format: #RRGGBB"
            )

        elif input_type == "file":
            raise AgentRedirectError(
                "This file input cannot be clicked. Use agentType(<value>, <same bbox>), with this format: /path/to/file"  # noqa: E501
            )

        elif input_type == "range":
            # Get min and max values from the range input
            range_min = element_info.get("attributes", {}).get("min", "0")
            range_max = element_info.get("attributes", {}).get("max", "100")
            raise AgentRedirectError(
                f"This range input cannot be clicked. Use agentType(<value>, <same bbox>), with a value from {range_min} to {range_max}."  # noqa: E501
            )
