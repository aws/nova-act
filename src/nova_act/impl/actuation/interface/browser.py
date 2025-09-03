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
from strands.tools.decorator import DecoratedFunctionTool
from typing_extensions import Any, Self, Union, final

from nova_act.impl.actuation.interface.actuator import ActuatorBase
from nova_act.impl.actuation.interface.types.click_types import ClickOptions, ClickType
from nova_act.types.api.step import Observation

# Ref: https://github.com/python/typing/issues/182
JSONSerializable = Union[str, int, float, bool, None, dict[str, Any], list[Any]]


class BrowserObservation(Observation):
    """An Observation of a Browser Page.

    Required fields:
        activeURL: str
        browserDimensions: BrowserDimensions
        idToBboxMap: dict[int, Bbox]
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
    def provide(self) -> list[DecoratedFunctionTool[..., JSONSerializable]]:
        """Provide Actions for a BrowserActuatorBase."""
        return [
            self.agent_click,
            self.agent_scroll,
            self.agent_type,
            self.go_to_url,
            self._return,
            self.think,
            self.throw_agent_error,
            self.wait,
        ]

    @final
    @tool(name="agentClick")
    def agent_click(
        self: Self, box: str, click_type: ClickType | None = None, click_options: ClickOptions | None = None
    ) -> JSONSerializable:
        """Clicks the center of the specified box."""
        return self.actuator.agent_click(box, click_type, click_options)

    @final
    @tool(name="agentScroll")
    def agent_scroll(self: Self, direction: str, box: str, value: float | None = None) -> JSONSerializable:
        """Scrolls the element in the specified box in the specified direction.

        Valid directions are up, down, left, and right.
        """
        return self.actuator.agent_scroll(direction, box, value)

    @final
    @tool(name="agentType")
    def agent_type(self: Self, value: str, box: str, pressEnter: bool = False) -> JSONSerializable:
        """Types the specified value into the element at the center of the
        specified box.

        If desired, the agent can press enter after typing the string.
        """
        return self.actuator.agent_type(value, box, pressEnter)

    @final
    @tool(name="goToUrl")
    def go_to_url(self: Self, url: str) -> JSONSerializable:
        """Navigates to the specifed URL."""
        return self.actuator.go_to_url(url)

    @final
    @tool(name="return")
    def _return(self: Self, value: str | None) -> JSONSerializable:
        """Complete execution of the task and return to the user.

        Return can either be bare (no value) or a string literal.
        """
        return self.actuator._return(value)

    @final
    @tool(name="think")
    def think(self: Self, value: str) -> JSONSerializable:
        """Has no effect on the environment. Should be used for reasoning about the next action."""
        return self.actuator.think(value)

    @final
    @tool(name="throw new AgentError")
    def throw_agent_error(self: Self, value: str) -> JSONSerializable:
        """Used when the task requested by the user is not possible."""
        return self.actuator.throw_agent_error(value)

    @final
    @tool(name="wait")
    def wait(self: Self, seconds: float) -> JSONSerializable:
        """Pauses execution for the specified number of seconds."""
        return self.actuator.wait(seconds)


class BrowserActuatorBase(ActuatorBase):
    """An Actuator for Browser use."""

    domain = "browser-use"
    _action_provider: BrowserActionProvider | None = None

    @final
    def list_actions(self) -> list[DecoratedFunctionTool[..., Any]]:
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
    ) -> JSONSerializable:
        """Clicks the center of the specified box."""

    @abstractmethod
    def agent_scroll(self, direction: str, box: str, value: float | None = None) -> JSONSerializable:
        """Scrolls the element in the specified box in the specified direction.

        Valid directions are up, down, left, and right.
        """

    @abstractmethod
    def agent_type(self, value: str, box: str, pressEnter: bool = False) -> JSONSerializable:
        """Types the specified value into the element at the center of the
        specified box.

        If desired, the agent can press enter after typing the string.
        """

    @abstractmethod
    def go_to_url(self, url: str) -> JSONSerializable:
        """Navigates to the specified URL."""

    @abstractmethod
    def _return(self, value: str | None) -> JSONSerializable:
        """Complete execution of the task and return to the user.

        Return can either be bare (no value) or a string literal."""

    @abstractmethod
    def think(self, value: str) -> JSONSerializable:
        """Has no effect on the environment. Should be used for reasoning about the next action."""

    @abstractmethod
    def throw_agent_error(self, value: str) -> JSONSerializable:
        """Used when the task requested by the user is not possible."""

    @abstractmethod
    def wait(self, seconds: float) -> JSONSerializable:
        """Pauses execution for the specified number of seconds."""

    @abstractmethod
    def wait_for_page_to_settle(self) -> JSONSerializable:
        """Ensure the browser page is ready for the next Action."""

    @abstractmethod
    def take_observation(self) -> BrowserObservation:
        """Take an observation of the existing browser state."""
