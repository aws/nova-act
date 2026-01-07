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
from playwright.sync_api import Page

from nova_act.tools.browser.default.dom_actuation.dispatch_events_dict import DispatchEvents
from nova_act.tools.browser.default.util.element_helpers import DEEP_ELEMENT_FROM_POINT_JS


def dispatch_event_sequence(page: Page, point: dict[str, float], events_config: list[DispatchEvents]) -> None:
    """
    Dispatch a sequence of events to an element at the specified point.

    Args:
        page: Playwright Page
        point: Dictionary with x and y coordinates
        events_config: List of event configurations, each containing:
                      - type: Event type (e.g., "pointermove", "click")
                      - init: Dictionary of event initialization parameters
    """

    page.evaluate(
        """
        (args) => {
            %s
            const { point, eventsConfig } = args;
            const element = deepElementFromPoint(point.x, point.y);
            if (!element) {
                throw new Error(`No element found at coordinates (${point.x}, ${point.y})`);
            }
            for (const event of eventsConfig) {
                element.dispatchEvent(new Event(event.type, event.init));
            }
        }
        """
        % (DEEP_ELEMENT_FROM_POINT_JS,),
        {"point": point, "eventsConfig": events_config},
    )
