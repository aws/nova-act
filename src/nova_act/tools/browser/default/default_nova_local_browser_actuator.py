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
import functools
import time
from datetime import datetime, timezone
from typing import Any, Callable, Literal

from playwright.sync_api import Page

from nova_act.tools.browser.default.playwright import PlaywrightInstanceManager
from nova_act.tools.browser.default.playwright_instance_options import PlaywrightInstanceOptions
from nova_act.tools.browser.default.util.agent_click import agent_click
from nova_act.tools.browser.default.util.agent_hover import agent_hover
from nova_act.tools.browser.default.util.agent_scroll import agent_scroll
from nova_act.tools.browser.default.util.agent_type import agent_type
from nova_act.tools.browser.default.util.bbox_parser import parse_bbox_string
from nova_act.tools.browser.default.util.go_to_url import go_to_url
from nova_act.tools.browser.default.util.take_observation import take_observation
from nova_act.tools.browser.default.util.wait import WAIT_FOR_PAGE_TO_SETTLE_CONFIG, wait_for_page_to_settle
from nova_act.tools.browser.interface.browser import (
    BrowserActuatorBase,
    BrowserObservation,
)
from nova_act.tools.browser.interface.playwright_pages import PlaywrightPageManagerBase
from nova_act.tools.browser.interface.types.click_types import ClickOptions
from nova_act.tools.browser.interface.types.scroll_types import ScrollDirection
from nova_act.types.api.step import BboxTLWH
from nova_act.types.errors import (
    ClientNotStarted,
    InvalidCertificate,
    InvalidURL,
)
from nova_act.types.guardrail import GuardrailCallable
from nova_act.types.json_type import JSONType
from nova_act.util.common_js_expressions import Expressions

MAX_PAGE_EVALUATE_RETRIES = 3


# Catch and throw the error stored in the playwright instance manager if present as it's more informative
# Without this mechanism, the error for blocked call is reported as a generic failed page navigation in Playwright
def _check_ssl_error(func: Callable[..., Any]) -> Callable[..., Any]:  # type: ignore[explicit-any]
    @functools.wraps(func)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:  # type: ignore[explicit-any]
        if not hasattr(self, "_playwright_manager") or not self._playwright_manager.started:
            raise ClientNotStarted("Client is not started before actuation")

        self._playwright_manager.setup_ssl_validation_hook(self._playwright_manager.context)
        try:
            return func(self, *args, **kwargs)
        except Exception:
            ssl_error = self._playwright_manager.safe_site_validation_error
            if ssl_error and isinstance(ssl_error, (InvalidURL, InvalidCertificate)):
                raise ssl_error
            raise
        finally:
            # Clear any SSL error and disable hook
            self._playwright_manager.clear_ssl_error()
            self._playwright_manager.disable_ssl_validation_hook()

    return wrapper


class DefaultNovaLocalBrowserActuator(BrowserActuatorBase, PlaywrightPageManagerBase):
    """The Default Actuator for NovaAct Browser Use."""

    def __init__(
        self,
        playwright_options: PlaywrightInstanceOptions,
        state_guardrail: GuardrailCallable | None = None,
    ):
        self._playwright_manager = PlaywrightInstanceManager(playwright_options)
        self._state_guardrail = state_guardrail

    def start(self, **kwargs: Any) -> None:  # type: ignore[explicit-any]
        if not self._playwright_manager.started:
            if "session_logs_directory" in kwargs:
                self._playwright_manager.start(kwargs.get("session_logs_directory"))

    def stop(self, **kwargs: Any) -> None:  # type: ignore[explicit-any]
        if self.started:
            self._playwright_manager.stop()

    @property
    def started(self, **kwargs: Any) -> bool:  # type: ignore[explicit-any]
        return self._playwright_manager.started

    def get_page(self, index: int = -1) -> Page:
        return self._playwright_manager.get_page(index)

    @property
    def pages(self) -> list[Page]:
        return self._playwright_manager.context.pages

    @_check_ssl_error
    def agent_click(
        self,
        box: str,
        click_type: Literal["left", "left-double", "right"] | None = None,
        click_options: ClickOptions | None = None,
    ) -> JSONType:
        """Clicks the center of the specified box."""
        bbox = parse_bbox_string(box)
        agent_click(bbox, self._playwright_manager.main_page, click_type or "left", click_options)
        return None

    @_check_ssl_error
    def agent_hover(self, box: str) -> JSONType:
        """Hovers on the center of the specified box."""
        bbox = parse_bbox_string(box)
        agent_hover(bbox, self._playwright_manager.main_page)
        return None

    @_check_ssl_error
    def agent_scroll(self, direction: ScrollDirection, box: str, value: float | None = None) -> JSONType:
        """Scrolls the element in the specified box in the specified direction.

        Valid directions are up, down, left, and right.
        """
        bbox = parse_bbox_string(box)
        agent_scroll(self._playwright_manager.main_page, direction, bbox, value)
        return None

    @_check_ssl_error
    def agent_type(self, value: str, box: str, pressEnter: bool = False) -> JSONType:
        """Types the specified value into the element at the center of the
        specified box.

        If desired, the agent can press enter after typing the string.
        """
        bbox = parse_bbox_string(box)
        agent_type(
            bbox,
            value,
            self._playwright_manager.main_page,
            self._playwright_manager.modifier_key,
            "pressEnter" if pressEnter else None,
            allowed_file_upload_paths=self._playwright_manager.security_options.allowed_file_upload_paths,
        )
        return None

    @_check_ssl_error
    def go_to_url(self, url: str) -> JSONType:
        """Navigates to the specified URL."""

        try:
            go_to_url(
                url,
                self._playwright_manager.main_page,
                allowed_file_open_paths=self._playwright_manager.security_options.allowed_file_open_paths,
                state_guardrail=self._state_guardrail,
            )
        except InvalidURL as e:
            raise ValueError(str(e)) from e
        return None

    def _return(self, value: str | None) -> JSONType:
        """Complete execution of the task and return to the user.

        Return can either be bare (no value) or a string literal."""
        return value

    def think(self, value: str) -> JSONType:
        """Has no effect on the environment. Should be used for reasoning about the next action."""
        pass

    def throw_agent_error(self, value: str) -> JSONType:
        """Used when the task requested by the user is not possible."""
        return value

    @_check_ssl_error
    def wait(self, seconds: float) -> JSONType:
        """Pauses execution for the specified number of seconds."""
        if seconds < 0:
            raise ValueError("Seconds must be non-negative")
        if seconds == 0:
            self.wait_for_page_to_settle()
        else:
            time.sleep(seconds)
        return None

    @_check_ssl_error
    def wait_for_page_to_settle(self) -> JSONType:
        """Ensure the browser page is ready for the next Action."""
        wait_for_page_to_settle(self._playwright_manager.main_page, WAIT_FOR_PAGE_TO_SETTLE_CONFIG)
        return None

    @_check_ssl_error
    def take_observation(self) -> BrowserObservation:
        """Take an observation of the existing browser state."""

        dimensions = None
        user_agent = None

        for attempt in range(MAX_PAGE_EVALUATE_RETRIES):
            try:
                dimensions = self._playwright_manager.main_page.evaluate(Expressions.GET_VIEWPORT_SIZE.value)
                user_agent = self._playwright_manager.main_page.evaluate(Expressions.GET_USER_AGENT.value)
                break
            except Exception as e:
                wait_for_page_to_settle(self._playwright_manager.main_page, WAIT_FOR_PAGE_TO_SETTLE_CONFIG)
                if attempt == MAX_PAGE_EVALUATE_RETRIES - 1:  # Last attempt
                    # Cast it as RuntimeError but also surface the original cause.
                    raise RuntimeError(f"{type(e).__str__}: {e}") from e

        # At this point, dimensions and user_agent are guaranteed to be set
        # because either the try block succeeded or an exception was raised
        assert dimensions is not None
        assert user_agent is not None

        id_to_bbox_map: dict[int, BboxTLWH] = {}
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
