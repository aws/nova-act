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
from typing import Dict

from nova_act.impl.custom_actuation.playwright.dom_actuation.create_dom_events import (
    create_mouse_event_init,
    create_pointer_event_init,
)


def get_after_scroll_events(point: Dict[str, float]) -> list:
    """Get events for after scrolling."""
    return [
        {"type": "pointerout", "init": create_pointer_event_init(point, -1, 0)},
        {
            "type": "pointerleave",
            "init": create_pointer_event_init(point, -1, 0, False, False, False),
        },
        {"type": "mouseout", "init": create_mouse_event_init(point)},
        {
            "type": "mouseleave",
            "init": create_mouse_event_init(point, -1, 0, False, False, False),
        },
    ]
