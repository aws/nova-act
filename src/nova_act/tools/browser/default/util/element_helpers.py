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
import time

from playwright.sync_api import Locator, Page

from nova_act.tools.browser.interface.types.element_dict import ElementDict
from nova_act.util.logging import setup_logging

_LOGGER = setup_logging(__name__)


def blur(element_info: ElementDict, page: Page) -> None:
    try:
        element = locate_element(element_info, page)
        element.blur()
    except Exception as e:
        _LOGGER.debug(f"Error blurring element: {e}")
        return


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
    element_info: ElementDict = page.evaluate(
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


def find_file_input_element(page: Page, x: float, y: float) -> str | None:
    """Find file input selector if clicking triggers a file upload. Returns selector or None."""
    result: str | None = page.evaluate(
        """
        ([x, y]) => {
            const elem = document.elementFromPoint(x, y);
            if (!elem) return null;

            // Direct file input
            if (elem.tagName === 'INPUT' && elem.type === 'file') {
                return elem.id ? `#${elem.id}` : 'input[type="file"]';
            }

            // Check container for file input
            let container = elem.closest('.form-group, div[class*="upload"], div[class*="file"], label');
            if (!container) {
                // Only check form-wide for elements that are likely file upload triggers
                const isFileUploadElement = elem.tagName === 'LABEL' ||
                    (elem.textContent && /\b(upload|attach|browse|choose.*file)\b/i.test(elem.textContent));
                if (isFileUploadElement) {
                    container = elem.closest('form');
                }
            }
            if (container) {
                const fileInput = container.querySelector('input[type="file"]');
                if (fileInput) {
                    return fileInput.id ? `#${fileInput.id}` : 'input[type="file"]';
                }
            }

            // Check for upload keywords + any file input on page
            const uploadKeywords = ['upload', 'attach', 'browse', 'choose', 'select file', 'add file', 'drag an image'];
            const text = (elem.textContent || '').toLowerCase();
            const className = typeof elem.className === 'string' ? elem.className.toLowerCase() : '';
            const id = (elem.id || '').toLowerCase();

            const hasUploadKeyword = uploadKeywords.some(keyword =>
                text.includes(keyword) || className.includes(keyword) || id.includes(keyword)
            );

            if (hasUploadKeyword) {
                const fileInput = document.querySelector('input[type="file"]');
                if (fileInput) {
                    return fileInput.id ? `#${fileInput.id}` : 'input[type="file"]';
                }
            }

            return null;
        }
        """,
        [x, y],
    )
    return result


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
    if is_pdf_page(page):
        # Element focus does not work on pdfs so use a small sleep then assume success.
        time.sleep(0.1)
        return True

    result: bool = page.evaluate(
        """
        ([x, y]) => {
            const elem = document.elementFromPoint(x, y);
            return elem === document.activeElement;
        }
        """,
        [x, y],
    )
    return result


def is_pdf_page(page: Page) -> bool:
    # Not rigorous but a simple way to identify a pdf.
    return page.url.lower().endswith(".pdf")
