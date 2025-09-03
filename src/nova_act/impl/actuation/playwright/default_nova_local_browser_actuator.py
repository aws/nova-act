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
from typing import Any, Literal

from playwright.sync_api import Page

from nova_act.impl.actuation.interface.browser import (
    BrowserActuatorBase,
    BrowserObservation,
    JSONSerializable,
)
from nova_act.impl.actuation.interface.playwright_pages import PlaywrightPageManagerBase
from nova_act.impl.actuation.interface.types.click_types import ClickOptions
from nova_act.impl.actuation.playwright.util.agent_click import agent_click
from nova_act.impl.actuation.playwright.util.agent_scroll import agent_scroll
from nova_act.impl.actuation.playwright.util.agent_type import agent_type
from nova_act.impl.actuation.playwright.util.go_to_url import go_to_url
from nova_act.impl.actuation.playwright.util.take_observation import take_observation
from nova_act.impl.actuation.playwright.util.wait import WAIT_FOR_PAGE_TO_SETTLE_CONFIG, wait_for_page_to_settle
from nova_act.impl.playwright import PlaywrightInstanceManager
from nova_act.impl.playwright_instance_options import PlaywrightInstanceOptions
from nova_act.types.api.step import Bbox
from nova_act.util.common_js_expressions import Expressions

MAX_PAGE_EVALUATE_RETRIES = 3


class DefaultNovaLocalBrowserActuator(BrowserActuatorBase, PlaywrightPageManagerBase):
    """The Default Actuator for NovaAct Browser Use."""

    def __init__(
        self,
        playwright_options: PlaywrightInstanceOptions,
    ):
        self._playwright_manager = PlaywrightInstanceManager(playwright_options)

    def start(self, **kwargs: Any) -> None:
        if not self._playwright_manager.started:
            if "session_logs_directory" in kwargs:
                self._playwright_manager.start(kwargs.get("session_logs_directory"))

    def stop(self, **kwargs: Any) -> None:
        if self.started:
            self._playwright_manager.stop()

    @property
    def started(self, **kwargs: Any) -> bool:
        return self._playwright_manager.started

    def get_page(self, index: int = -1) -> Page:
        return self._playwright_manager.get_page(index)

    @property
    def pages(self) -> list[Page]:
        return self._playwright_manager.context.pages

    def agent_click(
        self,
        box: str,
        click_type: Literal["left", "left-double", "right"] | None = None,
        click_options: ClickOptions | None = None,
    ) -> JSONSerializable:
        """Clicks the center of the specified box."""
        agent_click(box, self._playwright_manager.main_page, click_type or "left", click_options)
        return None

    def agent_scroll(self, direction: str, box: str, value: float | None = None) -> JSONSerializable:
        """Scrolls the element in the specified box in the specified direction.

        Valid directions are up, down, left, and right.
        """
        agent_scroll(self._playwright_manager.main_page, direction, box, value)
        return None

    def agent_type(self, value: str, box: str, pressEnter: bool = False) -> JSONSerializable:
        """Types the specified value into the element at the center of the
        specified box.

        If desired, the agent can press enter after typing the string.
        """
        agent_type(box, value, self._playwright_manager.main_page, "pressEnter" if pressEnter else None)
        return None

    def go_to_url(self, url: str) -> JSONSerializable:
        """Navigates to the specified URL."""
        go_to_url(url, self._playwright_manager.main_page)
        return None

    def _return(self, value: str | None) -> JSONSerializable:
        """Complete execution of the task and return to the user.

        Return can either be bare (no value) or a string literal."""
        return value

    def think(self, value: str) -> JSONSerializable:
        """Has no effect on the environment. Should be used for reasoning about the next action."""
        pass

    def throw_agent_error(self, value: str) -> JSONSerializable:
        """Used when the task requested by the user is not possible."""
        return value

    def wait(self, seconds: float) -> JSONSerializable:
        """Pauses execution for the specified number of seconds."""
        if seconds < 0:
            raise ValueError("Seconds must be non-negative")
        if seconds == 0:
            self.wait_for_page_to_settle()
        else:
            time.sleep(seconds)
        return None

    def wait_for_page_to_settle(self) -> JSONSerializable:
        """Ensure the browser page is ready for the next Action."""
        wait_for_page_to_settle(self._playwright_manager.main_page, WAIT_FOR_PAGE_TO_SETTLE_CONFIG)
        return None

    def take_observation(self) -> BrowserObservation:
        """Take an observation of the existing browser state."""

        dimensions = None
        user_agent = None

        for attempt in range(MAX_PAGE_EVALUATE_RETRIES):
            try:
                dimensions = self._playwright_manager.main_page.evaluate(Expressions.GET_VIEWPORT_SIZE.value)
                user_agent = self._playwright_manager.main_page.evaluate(Expressions.GET_USER_AGENT.value)
                break
            except Exception:
                wait_for_page_to_settle(self._playwright_manager.main_page, WAIT_FOR_PAGE_TO_SETTLE_CONFIG)
                if attempt == MAX_PAGE_EVALUATE_RETRIES - 1:  # Last attempt
                    raise

        # At this point, dimensions and user_agent are guaranteed to be set
        # because either the try block succeeded or an exception was raised
        assert dimensions is not None
        assert user_agent is not None

        id_to_bbox_map: dict[int, Bbox] = {}
        simplified_dom = ""

        screenshot_data_url = take_observation(self._playwright_manager.main_page, dimensions)

        return {
            "activeURL": self._playwright_manager.main_page.url,
            "browserDimensions": {
                "scrollHeight": dimensions["scrollHeight"],
                "scrollLeft": dimensions["scrollLeft"],
                "scrollTop": dimensions["scrollTop"],
                "scrollWidth": dimensions["scrollWidth"],
                "windowHeight": dimensions["height"],
                "windowWidth": dimensions["width"],
            },
            "idToBboxMap": id_to_bbox_map,
            "screenshotBase64": screenshot_data_url,
            "simplifiedDOM": simplified_dom,
            "timestamp_ms": int(datetime.now(timezone.utc).timestamp() * 1000),
            "userAgent": user_agent,
        }
