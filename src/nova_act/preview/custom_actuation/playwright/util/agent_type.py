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

from nova_act.preview.custom_actuation.playwright.dom_actuation.type_events import get_after_type_events
from nova_act.preview.custom_actuation.playwright.util.bbox_parser import bounding_box_to_point, parse_bbox_string
from nova_act.preview.custom_actuation.playwright.util.dispatch_dom_events import dispatch_event_sequence
from nova_act.preview.custom_actuation.playwright.util.element_helpers import (
    blur,
    check_if_native_dropdown,
    get_element_at_point,
    locate_element,
)


def agent_type(
    bounding_box: str,
    value: str,
    page: Page,
    additional_options: str | None = None,
) -> None:
    bbox_dict = parse_bbox_string(bounding_box)
    point = bounding_box_to_point(bbox_dict)
    element_info = get_element_at_point(page, point["x"], point["y"])
    if not element_info:
        raise ValueError("No element found at the given point")

    if check_if_native_dropdown(page, point["x"], point["y"]):
        page.mouse.click(point["x"], point["y"])
        page.keyboard.type(value)
        page.keyboard.press("Enter")
        blur(element_info, page)
        return

    # click on the input box
    page.mouse.click(point["x"], point["y"])

    # clear the input using only playwright keyboard
    page.keyboard.press("ControlOrMeta+A")
    page.keyboard.press("Backspace")

    # type the value
    page.keyboard.type(value)

    if additional_options and additional_options == "pressEnter":
        page.keyboard.press("Enter")

    else:
        # blur the input box
        if element_info.get("blurField"):
            blur(element_info, page)

            element = locate_element(element_info, page)
            after_type_events = get_after_type_events(point)

            dispatch_event_sequence(element, after_type_events)
