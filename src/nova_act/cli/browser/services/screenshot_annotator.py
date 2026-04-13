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
"""Screenshot annotation service — overlay bounding boxes and ref labels on screenshots."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import Error as PlaywrightError

if TYPE_CHECKING:
    from playwright.sync_api import FloatRect, Page

    from nova_act.cli.browser.services.intent_resolution.snapshot import SnapshotElement

# Color-code by role
ROLE_COLORS: dict[str, str] = {
    "button": "#3B82F6",  # blue
    "link": "#22C55E",  # green
    "textbox": "#F97316",  # orange
    "searchbox": "#F97316",
    "combobox": "#F97316",
    "checkbox": "#A855F7",  # purple
    "radio": "#A855F7",
    "switch": "#A855F7",
    "slider": "#EAB308",  # yellow
    "spinbutton": "#EAB308",
    "tab": "#06B6D4",  # cyan
    "menuitem": "#06B6D4",
}
DEFAULT_COLOR = "#EF4444"  # red

INTERACTIVE_ROLES = frozenset(
    {
        "button",
        "link",
        "textbox",
        "checkbox",
        "radio",
        "combobox",
        "menuitem",
        "tab",
        "switch",
        "slider",
        "searchbox",
        "spinbutton",
    }
)

# Annotation rendering constants
FILL_ALPHA = 40
LABEL_BG_ALPHA = 200
OUTLINE_WIDTH = 2
LABEL_PADDING_X = 6
LABEL_PADDING_Y = 4
TEXT_OFFSET_X = 3
TEXT_OFFSET_Y = 1


def _color_for_role(role: str) -> str:
    return ROLE_COLORS.get(role, DEFAULT_COLOR)


def _hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


def annotate_screenshot(
    screenshot_bytes: bytes,
    elements_with_boxes: list[tuple[SnapshotElement, FloatRect]],
) -> bytes:
    """Overlay bounding boxes and ref labels on a screenshot.

    Args:
        screenshot_bytes: Raw PNG/JPEG screenshot bytes.
        elements_with_boxes: List of (SnapshotElement, bbox_dict) where bbox_dict
            has keys x, y, width, height.

    Returns:
        Annotated PNG image bytes.
    """
    img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = ImageFont.load_default()

    for elem, bbox in elements_with_boxes:
        x, y, w, h = bbox["x"], bbox["y"], bbox["width"], bbox["height"]
        color_hex = _color_for_role(elem.role)
        outline_color = _hex_to_rgba(color_hex)
        fill_color = _hex_to_rgba(color_hex, alpha=FILL_ALPHA)

        # Semi-transparent fill + solid outline
        draw.rectangle([x, y, x + w, y + h], fill=fill_color, outline=outline_color, width=OUTLINE_WIDTH)

        # Label background + text
        label = elem.ref
        label_bbox = font.getbbox(label)
        label_w = label_bbox[2] - label_bbox[0] + LABEL_PADDING_X
        label_h = label_bbox[3] - label_bbox[1] + LABEL_PADDING_Y
        label_bg = _hex_to_rgba(color_hex, alpha=LABEL_BG_ALPHA)
        draw.rectangle([x, y - label_h, x + label_w, y], fill=label_bg)
        draw.text((x + TEXT_OFFSET_X, y - label_h + TEXT_OFFSET_Y), label, fill=(255, 255, 255, 255), font=font)

    result = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    result.save(buf, format="PNG")
    return buf.getvalue()


def resolve_element_boxes(
    page: Page,
    elements: list[SnapshotElement],
    role_filter: frozenset[str] | None = None,
) -> list[tuple[SnapshotElement, FloatRect]]:
    """Resolve bounding boxes for snapshot elements via Playwright locators.

    Args:
        page: Playwright Page object.
        elements: Flattened snapshot elements.
        role_filter: If provided, only include elements with these roles.
            If None, defaults to INTERACTIVE_ROLES.

    Returns:
        List of (element, bbox_dict) for elements with valid bounding boxes.
    """
    allowed_roles = role_filter if role_filter is not None else INTERACTIVE_ROLES
    results: list[tuple[SnapshotElement, FloatRect]] = []

    for elem in elements:
        if not elem.role or elem.role not in allowed_roles:
            continue
        if not elem.name:
            continue
        try:
            locator = page.get_by_role(elem.role, name=elem.name).first  # type: ignore[arg-type]
            bbox = locator.bounding_box()
            if bbox:
                results.append((elem, bbox))
        except PlaywrightError:
            continue

    return results


def annotate_page_screenshot(
    active_page: Page,
    screenshot_bytes: bytes,
    annotate_filter: str | None = None,
) -> tuple[bytes, int]:
    """Annotate a screenshot with bounding boxes for interactive elements.

    Args:
        active_page: Playwright Page to get accessibility snapshot from.
        screenshot_bytes: Raw screenshot bytes to annotate.
        annotate_filter: Comma-separated roles to include, or None for all interactive roles.

    Returns:
        Tuple of (annotated_bytes, annotation_count).
    """
    from nova_act.cli.browser.services.intent_resolution.snapshot import flatten_snapshot

    tree = active_page.accessibility.snapshot()
    elements = flatten_snapshot(tree)

    role_filter: frozenset[str] | None = None
    if annotate_filter:
        role_filter = frozenset(r.strip() for r in annotate_filter.split(","))

    elements_with_boxes = resolve_element_boxes(active_page, elements, role_filter)
    annotation_count = len(elements_with_boxes)
    if elements_with_boxes:
        screenshot_bytes = annotate_screenshot(screenshot_bytes, elements_with_boxes)

    return screenshot_bytes, annotation_count
