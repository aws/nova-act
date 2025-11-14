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
from __future__ import annotations

from abc import abstractmethod

from strands import tool
from typing_extensions import Self, final

from nova_act.tools.actuator.interface.actuator import ActionType, ActuatorBase
from nova_act.tools.browser.interface.types.click_types import ClickOptions, ClickType
from nova_act.tools.browser.interface.types.scroll_types import ScrollDirection
from nova_act.types.api.step import Observation
from nova_act.types.json_type import JSONType


class BrowserObservation(Observation):
    """An Observation of a Browser Page.

    Required fields:
        activeURL: str
        browserDimensions: BrowserDimensions
        idToBboxMap: dict[int, BboxTLWH]
        simplifiedDOM: str
        timestamp_ms: int
        userAgent: str
        screenshotBase64: str

    """

    screenshotBase64: str


class BrowserActionProvider:
    """Provide the list of Actions for a BrowserActuatorBase implementation.

    Provides two utilities:
    1. Ensures that function signatures / descriptions are never modified during override
       and exactly match the model's expected format.
    2. Ensures the list of provided Actions exactly matches the model's expectation.

    """

    def __init__(self, actuator: BrowserActuatorBase):
        self.actuator = actuator

    @final
    def provide(self) -> list[ActionType]:
        """Provide Actions for a BrowserActuatorBase."""
        return [
            self.agent_click,
            self.agent_hover,
            self.agent_scroll,
            self.agent_type,
            self.go_to_url,
            self._return,
            self.think,
            self.throw_agent_error,
            self.wait,
            self.wait_for_page_to_settle,
            self.take_observation,
        ]

    @final
    @tool(name="agentClick")
    def agent_click(
        self: Self, box: str, click_type: ClickType | None = None, click_options: ClickOptions | None = None
    ) -> JSONType:
        """Clicks the center of the specified box."""
        return self.actuator.agent_click(box, click_type, click_options)

    @final
    @tool(name="agentHover")
    def agent_hover(self: Self, box: str) -> JSONType:
        """Hovers on the center of the specified box."""
        return self.actuator.agent_hover(box)

    @final
    @tool(name="agentScroll")
    def agent_scroll(self: Self, direction: ScrollDirection, box: str, value: float | None = None) -> JSONType:
        """Scrolls the element in the specified box in the specified direction.

        Valid directions are up, down, left, and right.
        """
        return self.actuator.agent_scroll(direction, box, value)

    @final
    @tool(name="agentType")
    def agent_type(self: Self, value: str, box: str, pressEnter: bool = False) -> JSONType:
        """Types the specified value into the element at the center of the
        specified box.

        If desired, the agent can press enter after typing the string.
        """
        return self.actuator.agent_type(value, box, pressEnter)

    @final
    @tool(name="goToUrl")
    def go_to_url(self: Self, url: str) -> JSONType:
        """Navigates to the specifed URL."""
        return self.actuator.go_to_url(url)

    @final
    @tool(name="return")
    def _return(self: Self, value: str | None) -> JSONType:
        """Complete execution of the task and return to the user.

        Return can either be bare (no value) or a string literal.
        """
        return self.actuator._return(value)

    @final
    @tool(name="think")
    def think(self: Self, value: str) -> JSONType:
        """Has no effect on the environment. Should be used for reasoning about the next action."""
        return self.actuator.think(value)

    @final
    @tool(name="throw")
    def throw_agent_error(self: Self, value: str) -> JSONType:
        """Used when the task requested by the user is not possible."""
        return self.actuator.throw_agent_error(value)

    @final
    @tool(name="wait")
    def wait(self: Self, seconds: float) -> JSONType:
        """Pauses execution for the specified number of seconds."""
        return self.actuator.wait(seconds)

    @final
    @tool(name="waitForPageToSettle")
    def wait_for_page_to_settle(self: Self) -> JSONType:
        """Ensure the browser page is ready for the next Action."""
        return self.actuator.wait_for_page_to_settle()

    @final
    @tool(name="takeObservation")
    def take_observation(self: Self) -> BrowserObservation:
        """Take an observation of the existing browser state."""
        return self.actuator.take_observation()


class BrowserActuatorBase(ActuatorBase):
    """
    An Actuator for Browser use.

    If an actuation method receives invalid arguments, it should raise ValueError. If it is not able to actuate due to
    an execution error, it should raise RuntimeError.
    """

    domain = "browser-use"
    _action_provider: BrowserActionProvider | None = None

    @final
    def list_actions(self) -> list[ActionType]:
        """List the valid Actions this Actuator can take."""
        if self._action_provider is None:
            self._action_provider = BrowserActionProvider(self)
        return self._action_provider.provide()

    @abstractmethod
    def agent_click(
        self,
        box: str,
        click_type: ClickType | None = None,
        click_options: ClickOptions | None = None,
    ) -> JSONType:
        """Clicks the center of the specified box."""

    @abstractmethod
    def agent_hover(self, box: str) -> JSONType:
        """Hovers on the center of the specified box."""

    @abstractmethod
    def agent_scroll(self, direction: ScrollDirection, box: str, value: float | None = None) -> JSONType:
        """Scrolls the element in the specified box in the specified direction.

        Valid directions are up, down, left, and right.
        """

    @abstractmethod
    def agent_type(self, value: str, box: str, pressEnter: bool = False) -> JSONType:
        """Types the specified value into the element at the center of the
        specified box.

        If desired, the agent can press enter after typing the string.
        """

    @abstractmethod
    def go_to_url(self, url: str) -> JSONType:
        """Navigates to the specified URL."""

    @abstractmethod
    def _return(self, value: str | None) -> JSONType:
        """Complete execution of the task and return to the user.

        Return can either be bare (no value) or a string literal."""

    @abstractmethod
    def think(self, value: str) -> JSONType:
        """Has no effect on the environment. Should be used for reasoning about the next action."""

    @abstractmethod
    def throw_agent_error(self, value: str) -> JSONType:
        """Used when the task requested by the user is not possible."""

    @abstractmethod
    def wait(self, seconds: float) -> JSONType:
        """Pauses execution for the specified number of seconds."""

    @abstractmethod
    def wait_for_page_to_settle(self) -> JSONType:
        """Ensure the browser page is ready for the next Action."""

    @abstractmethod
    def take_observation(self) -> BrowserObservation:
        """Take an observation of the existing browser state."""
