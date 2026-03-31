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

from dataclasses import dataclass


@dataclass
class SnapshotElement:
    """A flattened accessibility tree element with sequential ref."""

    ref: str
    role: str
    name: str
    value: str = ""
    disabled: bool = False
    checked: bool = False


def flatten_snapshot(tree: dict[str, object] | None) -> list[SnapshotElement]:
    """Flatten a Playwright accessibility snapshot tree into sequential elements.

    Performs depth-first traversal, assigning refs e1, e2, ... to each node.
    """
    if not tree:
        return []

    elements: list[SnapshotElement] = []
    counter = 0
    stack: list[dict[str, object]] = [tree]

    while stack:
        node = stack.pop()
        counter += 1
        elements.append(
            SnapshotElement(
                ref=f"e{counter}",
                role=str(node.get("role", "")),
                name=str(node.get("name", "")),
                value=str(node.get("value", "")),
                disabled=bool(node.get("disabled", False)),
                checked=bool(node.get("checked", False)),
            )
        )
        # Push children in reverse so left children are processed first
        children = node.get("children", [])
        if isinstance(children, list):
            for child in reversed(children):
                if isinstance(child, dict):
                    stack.append(child)

    return elements
