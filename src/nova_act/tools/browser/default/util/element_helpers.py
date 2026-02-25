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
from typing import Literal, TypedDict, TypeVar, cast

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


_T = TypeVar("_T")
"""Dynamic type for recurse_through_iframes inner_js return."""


def recurse_through_iframes(page: Page, x: float, y: float, inner_js: str, return_type: type[_T]) -> _T | None:
    """
    Starting from the main frame, drill through any iframes at the given
    viewport coordinates until we reach a frame where the element at (x, y)
    is NOT an iframe.

    The coordinate system works as follows:
    - The initial (x, y) are viewport coordinates relative to the main page.
    - Each iframe is positioned somewhere within its parent frame. When we
      drill into an iframe, we need to convert the coordinates from the
      parent's coordinate space to the iframe's coordinate space.
    - We do this by subtracting the iframe's top-left corner (rect.x, rect.y)
      from the current coordinates. For example, if the iframe starts at
      (100, 200) in the parent, and we're looking for the point (150, 250),
      then inside the iframe that point is at (50, 50).

    Args:
        page: Playwright page object
        x: X viewport coordinate
        y: Y viewport coordinate
        inner_js: JS code to execute once we've found a non-iframe element.
                  It has access to `elem` (the element found by deepElementFromPoint)
                  and `x`, `y` (the coordinates in the current frame's space).
                  Should return an object with `type_` set to something other
                  than 'iframe', or null.
        return_type: phantom type parameter to provide return type of inner_js

    Returns:
        The result of evaluating inner_js in the deepest reachable frame,
        or None if no element was found or an iframe couldn't be accessed.
    """
    current_frame = page.main_frame
    current_x, current_y = x, y

    while True:
        result = current_frame.evaluate(
            """
            ([x, y]) => {
                %s

                const elem = deepElementFromPoint(document, x, y);
                if (!elem) return null;

                // If the element is an iframe, we can't necessarily access its
                // contents from JavaScript (cross-origin policy), so we return
                // the iframe's metadata and let Python drill in via Playwright.
                if (elem.tagName === 'IFRAME') {
                    const r = elem.getBoundingClientRect();
                    return {
                        type_: 'iframe',
                        name: elem.getAttribute('name') || '',
                        // We need the iframe's position in the current frame so
                        // we can convert coordinates to the iframe's local space.
                        rect: {x: r.x, y: r.y, width: r.width, height: r.height}
                    };
                }

                // Not an iframe — run the caller's custom JS logic.
                %s
            }
            """
            % (DEEP_ELEMENT_FROM_POINT_JS, inner_js),
            [current_x, current_y],
        )

        if not isinstance(result, dict):
            # If we did not get a `dict` back from Page.evaluate, then
            # we did not successfully find an element.
            return None

        if result.get("type_") != "iframe":
            # We've reached a non-iframe element; return the result from
            # the caller's custom JS. We cast to their provided type.
            return cast(_T, result)

        # The element at this point is an iframe. We need to:
        # 1. Convert coordinates from the current frame's space to the
        #    iframe's local space by subtracting the iframe's position.
        rect = result["rect"]
        current_x -= rect["x"]
        current_y -= rect["y"]

        # 2. Find the matching Playwright Frame object so we can evaluate
        #    JavaScript inside the iframe (even if it's cross-origin).
        iframe_name = result["name"]
        target_frame = None
        for child_frame in current_frame.child_frames:
            if iframe_name and child_frame.name == iframe_name:
                target_frame = child_frame
                break

        if target_frame is None:
            _LOGGER.warning("Found iframe but could not access its child frame.")
            return None

        _LOGGER.debug(f"Drilling into iframe: {iframe_name[:80]}...")
        current_frame = target_frame


def get_element_at_point(page: Page, x: float, y: float) -> ElementDict | None:
    """
    Get the HTML element at the specified x,y coordinates,
    drilling into iframes (including cross-origin) as needed.

    Args:
        page: Playwright page object
        x: X coordinate
        y: Y coordinate

    Returns:
        Dictionary containing element information or None if no element found
    """

    class _ElementResult(TypedDict):
        """TypeGuard for injected JS."""

        type_: Literal["element"]
        value: ElementDict

    result = recurse_through_iframes(
        page,
        x,
        y,
        """
        const attributes = {};
        if (elem.attributes) {
            for (const attr of elem.attributes) {
                attributes[attr.name] = attr.value;
            }
        }

        return {
            type_: 'element',
            value: {
                tagName: elem.tagName,
                id: elem.id,
                className: elem.className,
                textContent: elem.textContent,
                attributes: attributes
            }
        };
        """,
        _ElementResult,
    )

    if not isinstance(result, dict) or result.get("type_") != "element":
        _LOGGER.warning(f"Could not find element at point {(x, y)}.")
        return None

    return result["value"]


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
