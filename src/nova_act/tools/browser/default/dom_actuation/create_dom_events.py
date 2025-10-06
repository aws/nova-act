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
from typing_extensions import TypedDict


class DomEvents(TypedDict):
    bubbles: bool
    button: int
    clientX: float
    clientY: float
    cancelable: bool
    composed: bool
    detail: int


def create_pointer_event_init(
    point: dict[str, float],
    button: int = -1,
    detail: int = 0,
    bubbles: bool = True,
    cancelable: bool = True,
    composed: bool = True,
) -> DomEvents:
    """Create initialization parameters for pointer events."""
    return {
        "bubbles": bubbles,
        "button": button,
        "cancelable": cancelable,
        "clientX": point["x"],
        "clientY": point["y"],
        "composed": composed,
        "detail": detail,
    }


def create_mouse_event_init(
    point: dict[str, float],
    button: int = 0,
    detail: int = 0,
    bubbles: bool = True,
    cancelable: bool = True,
    composed: bool = True,
) -> DomEvents:
    """Create initialization parameters for mouse events."""
    return {
        "bubbles": bubbles,
        "button": button,
        "cancelable": cancelable,
        "clientX": point["x"],
        "clientY": point["y"],
        "composed": composed,
        "detail": detail,
    }


def create_focus_event_init(bubbles: bool = False, cancelable: bool = False, composed: bool = True) -> dict[str, bool]:
    """Create initialization parameters for focus events."""
    return {"bubbles": bubbles, "cancelable": cancelable, "composed": composed}
