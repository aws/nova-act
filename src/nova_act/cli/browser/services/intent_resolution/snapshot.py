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
"""Accessibility snapshot flattening and element representation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from playwright.sync_api import Page


@dataclass
class SnapshotElement:
    """A flattened accessibility tree element with sequential ref."""

    ref: str
    role: str
    name: str
    value: str = ""
    disabled: bool = False
    checked: bool = False


# ---------------------------------------------------------------------------
# aria_snapshot based capture (replaces the removed page.accessibility.snapshot)
# ---------------------------------------------------------------------------
#
# TODO(playwright-upgrade): replace this aria_snapshot (YAML) + yaml.safe_load +
# label-parse path with page.ariaSnapshotJSON(), which returns structured
# role/name/flags/value/url/children directly (no YAML, no regex) in the shape
# SnapshotElement expects. It is not in Playwright 1.62.0 (main-branch only
# today); upstream microsoft/playwright#42169 makes the JSON snapshot the single
# source of truth and derives the YAML parsed here from it. Adopt it once it
# ships in a stable Playwright release within the supported range.
# Revisit when that lands.

# A node label looks like:  role "optional name" [attr] [attr] ...
# for example:  textbox "Search products" [ref=e4]   or   button "Pay now" [disabled]
_LABEL_RE = re.compile(r'^(?P<role>\S+)(?:\s+"(?P<name>(?:[^"\\]|\\.)*)")?(?P<attrs>.*)$')


def _emit(label: str, value: str, elements: list[SnapshotElement]) -> None:
    """Parse a single aria node label into a SnapshotElement and append it."""
    match = _LABEL_RE.match(label.strip())
    if match is None:
        return
    tokens = re.findall(r"\[([^\]]+)\]", match.group("attrs") or "")
    elements.append(
        SnapshotElement(
            ref=f"e{len(elements) + 1}",
            role=match.group("role"),
            name=(match.group("name") or "").replace('\\"', '"'),
            value=str(value or ""),
            disabled="disabled" in tokens,
            checked="checked" in tokens,
        )
    )


def _walk_aria(node: object, elements: list[SnapshotElement]) -> None:
    """Depth-first walk of a parsed aria snapshot, emitting one element per node."""
    if isinstance(node, list):
        for item in node:
            _walk_aria(item, elements)
    elif isinstance(node, dict):
        for key, value in node.items():
            # Keys beginning with "/" are node attributes (for example /url), not elements.
            if key.startswith("/"):
                continue
            # yaml.safe_load coerces unquoted scalars, so a node like `textbox "Zip": 90210`
            # parses the value as int/float/bool. Stringify those so bare numeric/boolean
            # field values are kept; containers and None (empty value) map to "".
            _emit(key, "" if value is None or isinstance(value, (list, dict)) else str(value), elements)
            if isinstance(value, list):
                _walk_aria(value, elements)
    elif isinstance(node, str):
        _emit(node, "", elements)


def snapshot_elements(page: Page) -> list[SnapshotElement]:
    """Capture the page accessibility tree and flatten it to SnapshotElements.

    Replaces the removed ``page.accessibility.snapshot()`` pipeline
    (``page.accessibility`` was removed in Playwright 1.57).
    ``Locator.aria_snapshot()`` returns a YAML document; we
    parse it with ``yaml.safe_load`` and emit the same ``SnapshotElement`` list
    the rest of the CLI browser expects, with refs assigned in depth-first
    order (e1, e2, ...).

    The ``aria_snapshot`` YAML looks like::

        - heading "Checkout" [level=1]
        - button "Submit order"
        - textbox "Search products": socks
        - checkbox "Gift wrap" [checked]
        - button "Pay now" [disabled]
        - link "Help":
            - /url: https://example.com

    Each node label is ``role "name" [attr] ...``: the accessible name is the
    quoted string, bracketed tokens carry state (``[checked]``, ``[disabled]``,
    ``[level=1]``, ``[ref=e4]``), and a scalar mapping value (``: socks``) is the
    element value. Keys beginning with ``/`` (for example ``/url``) are node
    attributes, not elements, and are skipped. The example above flattens to,
    among others, ``SnapshotElement(ref="e1", role="heading", name="Checkout")``,
    ``SnapshotElement(ref="e3", role="textbox", name="Search products",
    value="socks")``, and ``SnapshotElement(ref="e4", role="checkbox",
    name="Gift wrap", checked=True)``.
    """
    yaml_text = page.locator("body").aria_snapshot()
    # aria_snapshot is typed to return str; guard anyway so an unexpected value
    # cannot drive yaml.safe_load into an unbounded read loop.
    if not isinstance(yaml_text, str):
        return []
    try:
        tree = yaml.safe_load(yaml_text)
    except yaml.YAMLError:
        return []
    elements: list[SnapshotElement] = []
    _walk_aria(tree, elements)
    return elements
