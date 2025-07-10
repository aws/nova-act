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
from datetime import datetime, timezone
from typing import Literal

from nova_act.impl.playwright import PlaywrightInstanceManager
from nova_act.impl.playwright_instance_options import PlaywrightInstanceOptions
from nova_act.preview.custom_actuation.interface.actuator import action
from nova_act.preview.custom_actuation.interface.browser import (
    BrowserActuatorBase,
    BrowserObservation,
    JSONSerializable,
)
from nova_act.preview.custom_actuation.interface.types.bbox_dict import Bbox
from nova_act.preview.custom_actuation.interface.types.click_options import ClickOptions
from nova_act.preview.custom_actuation.interface.types.dimensions_dict import DimensionsDict
from nova_act.preview.custom_actuation.playwright.util.agent_click import agent_click
from nova_act.preview.custom_actuation.playwright.util.agent_scroll import agent_scroll
from nova_act.preview.custom_actuation.playwright.util.agent_type import agent_type
from nova_act.preview.custom_actuation.playwright.util.go_to_url import go_to_url
from nova_act.preview.custom_actuation.playwright.util.take_observation import take_observation
from nova_act.preview.custom_actuation.playwright.util.wait import wait_for_page_to_settle
from nova_act.util.common_js_expressions import Expressions


class DefaultNovaLocalBrowserActuator(BrowserActuatorBase):
    """The Default Actuator for NovaAct Browser Use."""

    def __init__(self, playwright_options: PlaywrightInstanceOptions):
        self._playwright_manager = PlaywrightInstanceManager(playwright_options)

    def start(self, **kwargs) -> None:
        if not self._playwright_manager.started:
            if "session_logs_directory" in kwargs:
                self._playwright_manager.start(kwargs.get("session_logs_directory"))

    def stop(self, **kwargs) -> None:
        if self.started:
            self._playwright_manager.stop()

    @property
    def started(self, **kwargs) -> bool:
        return self._playwright_manager.started

    @action
    def agent_click(
        self,
        box: str,
        click_type: Literal["left", "left-double", "right"] | None = None,
        click_options: ClickOptions | None = None,
    ) -> JSONSerializable:
        """Clicks the center of the specified box."""
        agent_click(box, self._playwright_manager.main_page, click_type or "left", click_options)
        return None

    @action
    def agent_scroll(self, direction: str, box: str, value: float | None = None) -> JSONSerializable:
        """Scrolls the element in the specified box in the specified direction.

        Valid directions are up, down, left, and right.
        """
        agent_scroll(self._playwright_manager.main_page, direction, box, value)
        return None

    @action
    def agent_type(self, value: str, box: str, pressEnter: bool = False) -> JSONSerializable:
        """Types the specified value into the element at the center of the
        specified box.

        If desired, the agent can press enter after typing the string.
        """
        agent_type(box, value, self._playwright_manager.main_page, "pressEnter" if pressEnter else None)
        return None

    @action
    def go_to_url(self, url: str) -> JSONSerializable:
        """Navigates to the specified URL."""
        go_to_url(url, self._playwright_manager.main_page)
        return None

    @action
    def _return(self, value: str | None) -> JSONSerializable:
        """Complete execution of the task and return to the user.

        Return can either be bare (no value) or a string literal."""
        return value

    @action
    def think(self, value: str) -> JSONSerializable:
        """Has no effect on the environment. Should be used for reasoning about the next action."""
        pass

    @action
    def throw_agent_error(self, value: str) -> JSONSerializable:
        """Used when the task requested by the user is not possible."""
        pass

    @action
    def wait(self, seconds: float) -> JSONSerializable:
        """Pauses execution for the specified number of seconds."""
        time.sleep(seconds)
        return None

    @action
    def wait_for_page_to_settle(
        self,
        options=None,
        save_screenshot: bool = False,
    ) -> JSONSerializable:
        """Ensure the browser page is ready for the next Action."""
        if options is None:
            options = {
                "max_timeout_ms": 180000,
                "number_of_checks": 3,
                "percent_difference_threshold": 25,
                "polling_interval_ms": 500,
                "start_time": datetime.now(timezone.utc),
            }
        wait_for_page_to_settle(self._playwright_manager.main_page, options, save_screenshot)
        return None

    @action
    def take_observation(
        self,
        save_screenshot: bool = False,
    ) -> BrowserObservation:
        """Take an observation of the existing browser state."""
        dimensions: DimensionsDict = self._playwright_manager.main_page.evaluate(Expressions.GET_VIEWPORT_SIZE.value)

        id_to_bbox_map: dict[int, Bbox] = {}
        simplified_dom = ""

        screenshot_data_url = take_observation(self._playwright_manager.main_page, dimensions, save_screenshot)

        return {
            "activeURL": self._playwright_manager.main_page.url,
            "browserDimensions": {
                "scrollHeight": 5845,
                "scrollLeft": 0,
                "scrollTop": 0,
                "scrollWidth": 1454,
                "windowHeight": dimensions["height"],
                "windowWidth": dimensions["width"],
            },
            "idToBboxMap": id_to_bbox_map,
            "screenshotBase64": screenshot_data_url,
            "simplifiedDOM": simplified_dom,
            "timestamp_ms": int(datetime.now(timezone.utc).timestamp() * 1000),
            "userAgent": self._playwright_manager.main_page.evaluate(Expressions.GET_USER_AGENT.value),
        }
