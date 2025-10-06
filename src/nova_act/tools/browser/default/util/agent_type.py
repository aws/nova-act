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
import os

from playwright.sync_api import Page

from nova_act.tools.browser.default.dom_actuation.type_events import get_after_type_events
from nova_act.tools.browser.default.util.bbox_parser import bounding_box_to_point, parse_bbox_string
from nova_act.tools.browser.default.util.dispatch_dom_events import dispatch_event_sequence
from nova_act.tools.browser.default.util.element_helpers import (
    blur,
    check_if_native_dropdown,
    find_file_input_element,
    get_element_at_point,
    is_element_focused,
    locate_element,
)
from nova_act.tools.browser.interface.types.element_dict import ElementDict
from nova_act.util.logging import setup_logging

_LOGGER = setup_logging(__name__)


def ensure_element_focus(page: Page, x: float, y: float, retries: int = 2) -> None:
    """
    Ensure the element at the given coordinates is focused before proceeding.
    If not focused, focus it first with retry logic.

    Args:
        page: Playwright page object
        x: X coordinate
        y: Y coordinate
        retries: Number of attempts to focus the element (default: 2)
    """
    for _ in range(retries):
        page.mouse.click(x, y)

        if is_element_focused(page, x, y):
            return

    raise ValueError(f"Failed to focus element at coordinates ({x}, {y}) after {retries} attempts")


def agent_type(
    bounding_box: str,
    value: str,
    page: Page,
    additional_options: str | None = None,
) -> None:
    bbox_dict = parse_bbox_string(bounding_box)
    point = bounding_box_to_point(bbox_dict)

    # Handle unorthodox file input first, before fixating on an element
    file_input_element = find_file_input_element(page, point["x"], point["y"])
    if file_input_element:
        handle_file_input(page, value, x=point["x"], y=point["y"], file_input_element=file_input_element)
        return

    element_info = get_element_at_point(page, point["x"], point["y"])
    if not element_info:
        raise ValueError("No element found at the given point")

    # Check for special input types first
    if element_info["tagName"].lower() == "input":
        input_type = element_info.get("attributes", {}).get("type", "").lower()
        if input_type == "color":
            handle_color_input(page, element_info, value)
            return
        elif input_type == "file":
            handle_file_input(page, value, element_info=element_info)
            return
        elif input_type == "range":
            handle_range_input(page, element_info, value)
            return

    # Handle native dropdown
    if check_if_native_dropdown(page, point["x"], point["y"]):
        page.mouse.click(point["x"], point["y"])
        page.keyboard.type(value)
        blur(element_info, page)
        return

    # Handle regular text input
    try:
        ensure_element_focus(page, point["x"], point["y"])
    except Exception as e:
        _LOGGER.debug(f"Element not focused: {e}")
        # If element is not in focus, don't continue the actuation
        return

    # Clear the input on Linux/Windows
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")

    # Clear the input on MacOS
    page.keyboard.press("Meta+A")
    page.keyboard.press("Backspace")

    if len(value) > 10:
        page.keyboard.insert_text(value)
    else:
        page.keyboard.type(value, delay=100)  # Types slower, like a user

    if additional_options and additional_options == "pressEnter":
        page.keyboard.press("Enter")
    else:
        # blur the input box
        if element_info.get("blurField"):
            try:
                blur(element_info, page)

                element = locate_element(element_info, page)
                after_type_events = get_after_type_events(point)

                dispatch_event_sequence(element, after_type_events)
            except Exception as e:
                _LOGGER.debug(f"Error blurring element: {e}")


def handle_color_input(page: Page, element_info: ElementDict, color_value: str) -> None:
    """
    Handle color input elements.

    Args:
        page: Playwright page object
        element_info: focused element
        color_value: Hex color value (e.g., "#ff6b6b" or "ff6b6b")
    """
    color_value = color_value.lstrip("#")
    if not (len(color_value) in (3, 6) and all(c in "0123456789abcdefABCDEF" for c in color_value)):
        raise ValueError(f"Invalid color value: {color_value}")
    color_value = "#" + color_value

    # Use JavaScript to set the color value directly
    try:
        element = locate_element(element_info, page)
        element.evaluate(f"(element) => element.value='{color_value}'")
    except Exception as e:
        _LOGGER.warning(f"Color input element not found: {e}")


def handle_file_input(
    page: Page,
    file_path: str,
    *,
    x: float | None = None,
    y: float | None = None,
    element_info: ElementDict | None = None,
    file_input_element: str | None = None,
) -> None:
    """
    Handle file input elements.

    Args:
        page: Playwright page object
        file_path: Path to the file to upload (can be absolute or relative)
        element_info: focused element
        x: X coordinate of the file input
        y: Y coordinate of the file input
        file_input_element: element pre-examined to be file input
    """

    if not os.path.isfile(file_path):
        raise ValueError(f"Not a regular file: {file_path}")

    # Get the file input element
    try:
        if file_input_element:
            # Case 1: We have a selector (from file upload context detection)
            try:
                page.locator(file_input_element).first.set_input_files(file_path)
            except Exception:
                # If that fails, click to create dynamic file input and retry
                if x is not None and y is not None:
                    page.mouse.click(x, y)
                    page.wait_for_timeout(100)
                page.locator(file_input_element).first.set_input_files(file_path)
        elif element_info:
            # Case 2: We have element info (direct file input)
            element = locate_element(element_info, page)
            element.set_input_files(file_path)
        else:
            raise ValueError("Must provide either file_input_element or element_info")
    except Exception as e:
        _LOGGER.warning(f"Error handling file input: {e}")


def handle_range_input(page: Page, element_info: ElementDict, range_value: str) -> None:
    """
    Handle range input elements.

    Args:
        page: Playwright page object
        x: X coordinate of the range input
        y: Y coordinate of the range input
        range_value: Numeric value for the range slider
    """
    try:
        float(range_value)
    except ValueError:
        raise ValueError(f"Invalid range value: {range_value}")

    # Get the range input element
    try:
        element = locate_element(element_info, page)
        # Use JavaScript to set the range value and trigger events
        element.evaluate(
            f"""(element) => {{
            element.value = '{range_value}';
            element.dispatchEvent(new Event('input'));
            element.dispatchEvent(new Event('change'));
        }}"""
        )
    except Exception:
        _LOGGER.warning("Range input element not found")
