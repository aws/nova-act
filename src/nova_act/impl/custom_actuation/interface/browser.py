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
from abc import abstractmethod

from typing_extensions import Any, TypedDict, Union

from nova_act.impl.custom_actuation.interface.actuator import ActuatorBase, action
from nova_act.impl.custom_actuation.interface.types.bbox_dict import Bbox

# Ref: https://github.com/python/typing/issues/182
JSONSerializable = Union[str, int, float, bool, None, dict[str, Any], list[Any]]


class BrowserObservation(TypedDict):
    """An Observation of a Browser Page."""

    activeURL: str
    browserDimensions: dict[str, int]
    idToBboxMap: dict[int, Bbox]
    screenshotBase64: str
    simplifiedDOM: str
    timestamp_ms: int
    userAgent: str


class BrowserActuatorBase(ActuatorBase):
    """An Actuator for Browser use."""

    domain = "browser-use"

    @action
    @abstractmethod
    def agent_click(
        self,
        box: str,
        click_type: str | None = None,
        click_options: str | None = None,
    ) -> JSONSerializable:
        """Clicks the center of the specified box."""

    @action
    @abstractmethod
    def agent_scroll(self, direction: str, box: str, value: float | None = None) -> JSONSerializable:
        """Scrolls the element in the specified box in the specified direction.

        Valid directions are up, down, left, and right.
        """

    @action
    @abstractmethod
    def agent_type(self, value: str, box: str, pressEnter: bool = False) -> JSONSerializable:
        """Types the specified value into the element at the center of the
        specified box.

        If desired, the agent can press enter after typing the string.
        """

    @action
    @abstractmethod
    def go_to_url(self, url: str) -> JSONSerializable:
        """Navigates to the specifed URL."""

    @action
    @abstractmethod
    def _return(self, value: str) -> JSONSerializable:
        """Complete execution of the task and return to the user.

        Return can either be bare (no value) or a string literal."""

    @action
    @abstractmethod
    def think(self, value: str) -> JSONSerializable:
        """Has no effect on the environment. Should be used for reasoning about the next action."""

    @action
    @abstractmethod
    def throw_agent_error(self, value: str) -> JSONSerializable:
        """Used when the task requested by the user is not possible."""

    @action
    @abstractmethod
    def wait(self, seconds: float) -> JSONSerializable:
        """Pauses execution for the specified number of seconds."""

    @action
    @abstractmethod
    def wait_for_page_to_settle(self) -> JSONSerializable:
        """Ensure the browser page is ready for the next Action."""

    @action
    @abstractmethod
    def take_observation(self) -> BrowserObservation:
        """Take an observation of the existing browser state."""
