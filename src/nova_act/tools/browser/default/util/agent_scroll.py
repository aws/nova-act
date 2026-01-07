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
from typing import NamedTuple

from playwright.sync_api import Page

from nova_act.tools.browser.default.dom_actuation.scroll_events import get_after_scroll_events
from nova_act.tools.browser.default.util.bbox_parser import bounding_box_to_point
from nova_act.tools.browser.default.util.dispatch_dom_events import dispatch_event_sequence
from nova_act.tools.browser.default.util.element_helpers import (
    is_pdf_page,
    viewport_dimensions,
)
from nova_act.tools.browser.interface.types.dimensions_dict import DimensionsDict
from nova_act.tools.browser.interface.types.scroll_types import ScrollDirection
from nova_act.types.api.step import BboxTLBR
from nova_act.util.logging import setup_logging

_LOGGER = setup_logging(__name__)


class ScrollElement(NamedTuple):
    bbox: BboxTLBR
    opaque: bool


def get_target_bbox_dimensions(bbox: BboxTLBR) -> DimensionsDict:
    dimensions: DimensionsDict = {
        "width": int(abs(bbox.left - bbox.right)),
        "height": int(abs(bbox.top - bbox.bottom)),
    }
    return dimensions


def get_scroll_element_bboxes_at(page: Page, bbox: BboxTLBR) -> list[ScrollElement] | None:
    point = bounding_box_to_point(bbox)
    # The javascript code below does the following:
    # 1. gets all html elements at the given point
    # 2. Iterates through all elements
    # 3. Verifies if element is scrollable by attempting to scroll the element and checking
    # if the scroll value has changed (canScroll()).
    # 4. Returns the first element that is scrollable, otherwise returns the dimensions of
    # the page.
    dimension_dicts: list[dict[str, int]] = page.evaluate(
        """
        ([x, y]) => {
            const elems = document.elementsFromPoint(x, y);
            if (elems.length === 0) return null;
            function canScroll(el, scrollAxis) {
                if (0 === el[scrollAxis]) {
                    el[scrollAxis] = 1;
                    if (1 === el[scrollAxis]) {
                        el[scrollAxis] = 0;
                        return true;
                    }
                } else {
                    return true;
                }
                return false;
            }

            function isScrollableX(el) {
                return (el.scrollWidth > el.clientWidth) && canScroll(el, 'scrollLeft');
            }

            function isScrollableY(el) {
                return (el.scrollHeight > el.clientHeight) && canScroll(el, 'scrollTop');
            }

            function isScrollable(el) {
                return isScrollableX(el) || isScrollableY(el);
            }
            function isOpaque(el) {
                return el.tagName.toLowerCase() === 'iframe' || !!el.shadowRoot;
            }
            function getVisibleRect(el) {
                if (!el || el.nodeType !== 1) return null;

                let rect = el.getBoundingClientRect();
                let left   = rect.left;
                let top    = rect.top;
                let right  = rect.right;
                let bottom = rect.bottom;

                // Helper: intersect with an element's *padding box* (visible scroller region)
                function clipWithElementPaddingBox(node) {
                    const r = node.getBoundingClientRect();
                    const clipLeft   = r.left + node.clientLeft;
                    const clipTop    = r.top  + node.clientTop;
                    const clipRight  = clipLeft + node.clientWidth;
                    const clipBottom = clipTop  + node.clientHeight;

                    left   = Math.max(left,   clipLeft);
                    top    = Math.max(top,    clipTop);
                    right  = Math.min(right,  clipRight);
                    bottom = Math.min(bottom, clipBottom);
                }

                // Walk up through potential clipping ancestors.
                // If inside shadow DOM, hop from ShadowRoot to its host.
                const stopAt = document.documentElement;

                // Use composed tree: cross shadow boundaries via .getRootNode().host
                let node = el.parentNode;
                while (node) {
                    // Exit once we've reached the chosen root
                    if (node === stopAt) {
                        clipWithElementPaddingBox(node);
                        break;
                    }

                    // If we encounter a ShadowRoot, continue at its host
                    if (node instanceof ShadowRoot) {
                        node = node.host;
                        continue;
                    }

                    if (node.nodeType === 1) {
                        const elem = node;
                        const cs = getComputedStyle(elem);

                        // Any overflow mode that can clip content
                        const clipsY = /(auto|scroll|hidden|clip)/.test(cs.overflowY) ||
                            /(auto|scroll|hidden|clip)/.test(cs.overflow);
                        const clipsX = /(auto|scroll|hidden|clip)/.test(cs.overflowX) ||
                            /(auto|scroll|hidden|clip)/.test(cs.overflow);

                        if (clipsX || clipsY) {
                            clipWithElementPaddingBox(elem);
                        }
                    }

                    node = node.parentNode || (node.getRootNode && node.getRootNode().host) || null;
                }

                // Finally, clip to the viewport
                const vpLeft = 0;
                const vpTop = 0;
                const vpRight = window.innerWidth;
                const vpBottom = window.innerHeight;

                left   = Math.max(left,   vpLeft);
                top    = Math.max(top,    vpTop);
                right  = Math.min(right,  vpRight);
                bottom = Math.min(bottom, vpBottom);

                // Check if the rectangle is still valid after clipping
                // If the element is completely clipped out, return null
                if (left >= right || top >= bottom) {
                    return null;
                }

                return {
                    top,
                    left,
                    right,
                    bottom,
                    opaque: isOpaque(el),
                };
            }
            function isWindowScrollable() {
                const doc = document.documentElement;
                const scrollableVertically = doc.scrollHeight > window.innerHeight;
                const scrollableHorizontally = doc.scrollWidth > window.innerWidth;
                return scrollableVertically || scrollableHorizontally;
            }

            const scrollableElements = [];
            for (let elem of elems) {
                if (elem.tagName.toLowerCase() === 'body' || elem.tagName.toLowerCase() === 'html') {
                    continue;
                }
                if (isOpaque(elem) ||
                    (elem.clientWidth > 0 && elem.clientHeight > 0 && isScrollable(elem))) {
                    let visibleRect = getVisibleRect(elem);
                    if (visibleRect !== null) {
                        scrollableElements.push(visibleRect);
                    }
                }
            }
            if (scrollableElements.length == 0 || isWindowScrollable()) {
                scrollableElements.push({
                    top: 0,
                    left: 0,
                    bottom: window.innerHeight,
                    right: window.innerWidth,
                    opaque: false
                });
            }

            return scrollableElements;
        }
        """,
        [point["x"], point["y"]],
    )

    if dimension_dicts is None:
        _LOGGER.warning(f"Could not find element at point {point}.")
        return

    dimensions = [
        ScrollElement(BboxTLBR(elt["top"], elt["left"], elt["bottom"], elt["right"]), bool(elt["opaque"]))
        for elt in dimension_dicts
    ]

    return dimensions


def scroll(delta: float, direction: ScrollDirection, page: Page) -> None:
    if direction == "up":
        page.mouse.wheel(0, -delta)
    elif direction == "down":
        page.mouse.wheel(0, delta)
    elif direction == "left":
        page.mouse.wheel(-delta, 0)
    elif direction == "right":
        page.mouse.wheel(delta, 0)


def calculate_scroll_amount(dimensions: DimensionsDict, direction: ScrollDirection, value: float | None) -> float:
    if value is None:
        if direction == "up" or direction == "down":
            return dimensions["height"] * 0.75
        elif direction == "left" or direction == "right":
            return dimensions["width"] * 0.75
        else:
            raise ValueError(f"Invalid direction {direction}")
    else:
        return value


def agent_scroll(
    page: Page,
    direction: ScrollDirection,
    bbox: BboxTLBR,
    value: float | None = None,
) -> None:
    bbox.validate_in_viewport(**viewport_dimensions(page))
    scroll_element_dimensions = get_scroll_element_bboxes_at(page, bbox)
    if scroll_element_dimensions is None:
        # Not possible to actuate.
        return
    if value is not None and value < 0:
        raise ValueError(f"Scroll value is negative {value}")

    best_scroll_elt = scroll_element_dimensions[0]

    best_bbox = best_scroll_elt.bbox

    delta = calculate_scroll_amount(
        DimensionsDict(width=int(best_bbox.right - best_bbox.left), height=int(best_bbox.bottom - best_bbox.top)),
        direction,
        value,
    )

    # Use the centroid of the bbox.
    point = bounding_box_to_point(bbox)
    page.mouse.move(point["x"], point["y"])
    if is_pdf_page(page):
        # First click to focus the pdf.
        page.mouse.click(point["x"], point["y"])

    scroll(delta, direction, page)

    if not best_scroll_elt.opaque:
        try:
            after_scroll_events = get_after_scroll_events(point)
            dispatch_event_sequence(page, point, after_scroll_events)
        except Exception as e:
            _LOGGER.debug(f"Error dispatching after scroll events: {e}")
            # Catch all exceptions when dispatching after scroll events so react loop does not stop
            return
