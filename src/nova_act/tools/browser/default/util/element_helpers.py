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
from enum import Enum

from playwright.sync_api import Locator, Page

from nova_act.tools.browser.interface.types.dimensions_dict import DimensionsDict
from nova_act.tools.browser.interface.types.element_dict import ElementDict
from nova_act.util.common_js_expressions import Expressions
from nova_act.util.logging import setup_logging

_LOGGER = setup_logging(__name__)


DEEP_ELEMENT_FROM_POINT_JS = """
function deepElementFromPoint(root, x, y, depth = 0) {
    // Prevent infinite recursion by limiting depth
    if (depth > 50) return null;

    let elem = root.elementFromPoint(x, y);
    if (!elem) return null;

    // Don't dive into shadow DOM if we found a select element
    if (elem.tagName && elem.tagName.toLowerCase() === "select") {
        return elem;
    }

    // Dive into shadow DOM
    if (elem.shadowRoot) {
        const shadowHit = deepElementFromPoint(elem.shadowRoot, x, y, depth + 1);
        if (shadowHit) return shadowHit;
    }

    // Dive into iframes
    if (elem.tagName === "IFRAME") {
        try {
            const rect = elem.getBoundingClientRect();
            const frameDoc = elem.contentDocument;
            if (frameDoc) {
                const innerHit = deepElementFromPoint(frameDoc, x - rect.left, y - rect.top, depth + 1);
                if (innerHit) return innerHit;
            }
        } catch (err) {
            // Cross-origin iframe, can't access
        }
    }

    return elem;
}
"""


def viewport_dimensions(page: Page) -> DimensionsDict:
    viewport = page.evaluate(Expressions.GET_VIEWPORT_SIZE.value)
    return {"height": viewport["height"], "width": viewport["width"]}


def blur(point: dict[str, float], page: Page) -> None:
    page.evaluate(
        """
        ([x, y]) => {
            %s
            const elem = deepElementFromPoint(document, x, y);
            if (!elem) return null;
            elem.blur();
        }
        """
        % (DEEP_ELEMENT_FROM_POINT_JS,),
        [point["x"], point["y"]],
    )


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


def get_element_at_point(page: Page, x: float, y: float) -> ElementDict | None:
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
            %s
            const elem = deepElementFromPoint(document, x, y);
            if (!elem) return null;

            const attributes = {};
            if (elem.attributes) {
                for (const attr of elem.attributes) {
                    attributes[attr.name] = attr.value;
                }
            }

            return {
                tagName: elem.tagName,
                id: elem.id,
                className: elem.className,
                textContent: elem.textContent,
                attributes: attributes
            };
        }
        """
        % (DEEP_ELEMENT_FROM_POINT_JS,),
        [x, y],
    )

    if element_info is None:
        _LOGGER.warning(f"Could not find element at point {(x, y)}.")
        return

    return element_info


def check_if_native_dropdown(page: Page, x: float, y: float) -> bool:
    element_info = get_element_at_point(page, x, y)
    if element_info is None:
        return False

    # Check if the element itself is a select
    if element_info["tagName"].lower() == "select":
        return True

    # Also check if we need to traverse up to find a parent select (for shadow DOM/iframe cases)
    result: bool = page.evaluate(
        """
        ([x, y]) => {
            %s
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

            const hitElement = deepElementFromPoint(document, x, y);
            if (!hitElement) return false;
            return !!findNearestSelect(hitElement);
        }
        """
        % (DEEP_ELEMENT_FROM_POINT_JS,),
        [x, y],
    )
    return result


class FocusState(Enum):
    """Represents the focus state of the page."""

    NO = "NO"  # Focus is on body/documentElement (not meaningful)
    MEANINGFUL_ELEMENT = "MEANINGFUL_ELEMENT"  # Focus is on a meaningful element but not under x,y
    UNDER_XY = "UNDER_XY"  # Focus is under the x,y coordinates


def is_element_focused(page: Page, x: float, y: float) -> FocusState:
    """
    Check if the element or one of its children at the given coordinates is currently focused.

    Args:
        page: Playwright page object
        x: X coordinate
        y: Y coordinate

    Returns:
        FocusState enum:
            - UNDER_XY: Element at x,y contains the active element
            - MEANINGFUL_ELEMENT: Active element is meaningful (not body/documentElement) but not under x,y
            - NO: Focus is on body or documentElement (not meaningful)
    """
    if is_pdf_page(page):
        # Element focus does not work on pdfs so use a small sleep then assume success.
        time.sleep(0.1)
        return FocusState.MEANINGFUL_ELEMENT

    result: dict[str, bool] = page.evaluate(
        """
        ([x, y]) => {
            %s
            const elem = deepElementFromPoint(document, x, y);
            function getDeepActiveElement() {
                let active = document.activeElement;

                while (active) {
                    // Shadow DOM
                    if (active.shadowRoot && active.shadowRoot.activeElement) {
                        active = active.shadowRoot.activeElement;
                        continue;
                    }

                    // Iframe (same-origin only)
                    if (active.tagName === "IFRAME") {
                        try {
                            const iframeDoc = active.contentDocument;
                            if (iframeDoc && iframeDoc.activeElement) {
                                active = iframeDoc.activeElement;
                                continue;
                            }
                        } catch {
                            // Cross-origin iframe
                        }
                    }

                    break;
                }

                return active;
            }
            const activeElement = getDeepActiveElement();
            const isFocusedXY = elem.contains(activeElement);
            const hasMeaningfulFocus = activeElement !== document.body && activeElement !== document.documentElement;
            return { isFocusedXY, hasMeaningfulFocus };
        }
        """
        % (DEEP_ELEMENT_FROM_POINT_JS,),
        [x, y],
    )

    if result["isFocusedXY"]:
        return FocusState.UNDER_XY
    elif result["hasMeaningfulFocus"]:
        return FocusState.MEANINGFUL_ELEMENT
    else:
        return FocusState.NO


def is_pdf_page(page: Page) -> bool:
    # Not rigorous but a simple way to identify a pdf.
    return page.url.lower().endswith(".pdf")
