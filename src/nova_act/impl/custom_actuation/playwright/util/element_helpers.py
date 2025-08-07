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
from playwright.sync_api import Locator, Page

from nova_act.impl.custom_actuation.interface.types.element_dict import ElementDict


def blur(element_info: ElementDict, page: Page) -> None:
    element = locate_element(element_info, page)
    element.blur()


def locate_element(element_info: ElementDict, page: Page) -> Locator:
    # Check if 'id' key exists and is not an empty string
    if "id" in element_info and element_info["id"] != "":
        element = page.locator(f"id={element_info['id']}").first
        if element:
            return element

    # If no element found by id, try to locate by class
    if "className" in element_info and element_info["className"] != "" and element_info["className"]:
        classNames = element_info["className"].split()
        class_selector = "." + ".".join(classNames)
        element = page.locator(class_selector).first
        if element:
            return element

    # If no element found by class, try to locate by tag name
    if "tagName" in element_info and element_info["tagName"] != "":
        element = page.locator(element_info["tagName"]).first
        if element:
            return element

    raise ValueError(f"Element not found: {element_info}")


def get_element_at_point(page: Page, x: float, y: float) -> ElementDict:
    """
    Get the HTML element at the specified x,y coordinates.

    Args:
        page: Playwright page object
        x: X coordinate
        y: Y coordinate

    Returns:
        Dictionary containing element information or None if no element found
    """
    # Execute JavaScript to get the element at the specified point
    element_info = page.evaluate(
        """
        ([x, y]) => {
            const elem = document.elementFromPoint(x, y);
            if (!elem) return null;
            return {
                tagName: elem.tagName,
                id: elem.id,
                className: elem.className,
                textContent: elem.textContent,
                attributes: Object.fromEntries(
                    [...elem.attributes].map(attr => [attr.name, attr.value])
                )
            };
        }
        """,
        [x, y],
    )

    if element_info is None:
        raise ValueError(f"Could not find element at point {(x, y)}.")

    return element_info


def check_if_native_dropdown(page: Page, x: float, y: float) -> bool:
    element_info = get_element_at_point(page, x, y)
    if element_info is None:
        raise ValueError("No element found at point")

    if element_info["tagName"].lower() == "select":
        return True

    return False


def is_element_focused(page: Page, x: float, y: float) -> bool:
    """
    Check if the element at the given coordinates is currently focused.

    Args:
        page: Playwright page object
        x: X coordinate
        y: Y coordinate

    Returns:
        True if the element is focused, False otherwise
    """
    return page.evaluate(
        """
        ([x, y]) => {
            const elem = document.elementFromPoint(x, y);
            return elem === document.activeElement;
        }
        """,
        [x, y],
    )
