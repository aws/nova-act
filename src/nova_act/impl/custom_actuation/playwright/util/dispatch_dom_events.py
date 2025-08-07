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
from playwright.sync_api import Locator


def dispatch_event_sequence(element: Locator, events_config: list) -> None:
    """
    Dispatch a sequence of events to an element.

    Args:
        element: Playwright ElementHandle
        events_config: List of event configurations, each containing:
                      - type: Event type (e.g., "pointermove", "click")
                      - init: Dictionary of event initialization parameters
    """

    for event in events_config:
        element.dispatch_event(event["type"], event["init"])
