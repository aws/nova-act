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
from playwright.sync_api import Page

from nova_act.impl.custom_actuation.interface.types.dimensions_dict import DimensionsDict
from nova_act.impl.custom_actuation.playwright.dom_actuation.scroll_events import get_after_scroll_events
from nova_act.impl.custom_actuation.playwright.util.bbox_parser import bounding_box_to_point, parse_bbox_string
from nova_act.impl.custom_actuation.playwright.util.dispatch_dom_events import dispatch_event_sequence
from nova_act.impl.custom_actuation.playwright.util.element_helpers import get_element_at_point, locate_element
from nova_act.util.common_js_expressions import Expressions
from nova_act.util.logging import setup_logging

_LOGGER = setup_logging(__name__)


def get_target_bbox_dimensions(bounding_box: str | None) -> DimensionsDict | None:
    if bounding_box is None:
        return None
    bbox_dict = parse_bbox_string(bounding_box)

    dimensions: DimensionsDict = {
        "width": int(abs(bbox_dict["left"] - bbox_dict["right"])),
        "height": int(abs(bbox_dict["top"] - bbox_dict["bottom"])),
    }
    return dimensions


def get_scroll_element_dimensions(page: Page, bounding_box: str | None = None) -> DimensionsDict:
    # No bounding box means we want to scroll the window
    if bounding_box is None:
        dimensions = page.evaluate(
            """() => {
            return {
                width: document.documentElement.clientWidth,
                height: document.documentElement.clientHeight,
            }
            }"""
        )
        return dimensions

    bbox_dict = parse_bbox_string(bounding_box)
    point = bounding_box_to_point(bbox_dict)
    dimensions = page.evaluate(
        """
        ([x, y]) => {
            const elem = document.elementFromPoint(x, y);
            if (!elem) return null;
            var hasHorizontalScrollbar = elem.scrollWidth > elem.clientWidth;
            var hasVerticalScrollbar = elem.scrollHeight > elem.clientHeight;
            if (elem.clientWidth == 0 || elem.clientHeight == 0 || (!hasHorizontalScrollbar && !hasVerticalScrollbar)) {
                return {
                    width: document.documentElement.clientWidth,
                    height: document.documentElement.clientHeight,
                }
            } else {
                return {
                    width: elem.clientWidth,
                    height: elem.clientHeight,
                }
            }
        }
        """,
        [point["x"], point["y"]],
    )

    if dimensions is None:
        raise ValueError(f"Could not find element at point {point}.")

    return dimensions


def scroll(delta: float, direction: str, page: Page) -> None:
    if direction == "up":
        page.mouse.wheel(0, -delta)
    elif direction == "down":
        page.mouse.wheel(0, delta)
    elif direction == "left":
        page.mouse.wheel(-delta, 0)
    elif direction == "right":
        page.mouse.wheel(delta, 0)


def agent_scroll(
    page: Page,
    direction: str,
    bounding_box: str | None = None,
    value: float | None = None,
) -> None:
    scroll_element_dimensions = get_scroll_element_dimensions(page, bounding_box)
    visible_area_dimensions = page.evaluate(Expressions.GET_VIEWPORT_SIZE.value)
    target_bbox_dimensions = get_target_bbox_dimensions(bounding_box)
    dimensions = scroll_element_dimensions

    # Compare with visible_area_dimensions
    dimensions["width"] = min(dimensions["width"], visible_area_dimensions["width"])
    dimensions["height"] = min(dimensions["height"], visible_area_dimensions["height"])

    # Compare with target_bbox_dimensions if it exists
    if target_bbox_dimensions is not None:
        dimensions["width"] = min(dimensions["width"], target_bbox_dimensions["width"])
        dimensions["height"] = min(dimensions["height"], target_bbox_dimensions["height"])

    delta = value
    if delta is None:
        if direction == "up" or direction == "down":
            delta = dimensions["height"] * 0.75
        elif direction == "left" or direction == "right":
            delta = dimensions["width"] * 0.75
        else:
            raise ValueError(f"Invalid direction {direction}")

    if bounding_box:
        bbox_dict = parse_bbox_string(bounding_box)
        point = bounding_box_to_point(bbox_dict)
        page.mouse.move(point["x"], point["y"])

    scroll(delta, direction, page)

    if bounding_box:
        bbox_dict = parse_bbox_string(bounding_box)

        is_entire_page = (
            bbox_dict["left"] == 0
            and bbox_dict["top"] == 0
            and bbox_dict["right"] >= visible_area_dimensions["width"] - 1
            and bbox_dict["bottom"] >= visible_area_dimensions["height"] - 1
        )

        if not is_entire_page:
            try:
                point = bounding_box_to_point(bbox_dict)
                element_info = get_element_at_point(page, point["x"], point["y"])
                if element_info is None:
                    return

                element = locate_element(element_info, page)

                after_scroll_events = get_after_scroll_events(point)

                dispatch_event_sequence(element, after_scroll_events)
            except Exception as e:
                _LOGGER.debug(f"Error dispatching after scroll events: {e}")
                # Catch all exceptions when dispatching after scroll events so react loop does not stop
                return
