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
import time

from playwright.sync_api import Page

from nova_act.tools.browser.default.util.bbox_parser import bounding_box_to_point
from nova_act.tools.browser.default.util.element_helpers import (
    FocusState,
    blur,
    check_if_native_dropdown,
    get_element_at_point,
    is_element_focused,
    locate_element,
    viewport_dimensions,
)
from nova_act.tools.browser.default.util.file_upload_helpers import click_and_maybe_return_file_chooser
from nova_act.tools.browser.interface.types.element_dict import ElementDict
from nova_act.types.api.step import BboxTLBR
from nova_act.util.logging import setup_logging
from nova_act.util.path_validator import validate_file_upload_path

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
    focus_state = FocusState.NO
    for _ in range(retries):
        page.mouse.click(x, y)

        focus_state = is_element_focused(page, x, y)
        if focus_state == FocusState.UNDER_XY:
            return
        time.sleep(0.5)

    if focus_state == FocusState.NO:
        raise RuntimeError(f"Failed to focus element at coordinates ({x}, {y}) after {retries} attempts")
    # If it's focused on a meaningful element, let pass.


def agent_type(
    bbox: BboxTLBR,
    value: str,
    page: Page,
    modifier_key: str,
    additional_options: str | None = None,
    allowed_file_upload_paths: list[str] = [],
) -> None:
    bbox.validate_in_viewport(**viewport_dimensions(page))
    point = bounding_box_to_point(bbox)

    if os.path.isfile(value):
        # If trying to upload, check if there's a file chooser and if so, upload
        chooser = click_and_maybe_return_file_chooser(
            page,
            x=point["x"],
            y=point["y"],
            timeout_ms=1500,
        )
        if chooser is not None:
            # Validate file upload path against allowlist
            validate_file_upload_path(value, allowed_file_upload_paths)

            chooser.set_files(value)
            return

    element_info = get_element_at_point(page, point["x"], point["y"])
    if not element_info:
        return

    # Check for special input types first
    if element_info["tagName"].lower() == "input":
        input_type = element_info.get("attributes", {}).get("type", "").lower()
        if input_type == "color":
            handle_color_input(page, element_info, value)
            return
        elif input_type == "file":
            handle_file_input(
                page, value, element_info=element_info, allowed_file_upload_paths=allowed_file_upload_paths
            )
            return
        elif input_type == "range":
            handle_range_input(page, element_info, value)
            return

    # Handle native dropdown
    if check_if_native_dropdown(page, point["x"], point["y"]):
        page.mouse.click(point["x"], point["y"])
        page.keyboard.type(value)
        blur(point, page)
        return

    # Handle regular text input
    try:
        ensure_element_focus(page, point["x"], point["y"])
    except Exception as e:
        _LOGGER.warning(f"Element not focused: {e}")
        # If element is not in focus, don't continue the actuation
        return

    page.keyboard.press(f"{modifier_key}+A")
    page.keyboard.press("Delete")

    if len(value) > 10:
        page.keyboard.insert_text(value)
    else:
        page.keyboard.type(value, delay=100)  # Types slower, like a user

    if additional_options and additional_options == "pressEnter":
        page.keyboard.press("Enter")


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
    allowed_file_upload_paths: list[str] = [],
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
        allowed_file_upload_paths: List of allowed path patterns for file uploads
    """
    # Validate file upload path against allowlist
    validate_file_upload_path(file_path, allowed_file_upload_paths)

    if not os.path.isfile(file_path):
        raise ValueError(f"Not a regular file or path does not exist: '{file_path}'")

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
            raise RuntimeError("Must provide either file_input_element or element_info")
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
