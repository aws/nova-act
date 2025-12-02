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
"""
Abstract interface for human input during React loop execution.

This interface allows clients to implement custom handlers for situations where
human input is required, such as solving CAPTCHAs or providing clarification
when the agent encounters errors.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import final

from strands import tool

from nova_act.tools.actuator.interface.actuator import ActionType
from nova_act.types.act_errors import ApproveCanceledError, NoHumanInputToolAvailable, UiTakeoverCanceledError
from nova_act.util.human_wait_time_tracker import HumanWaitTimeTracker


class _NullWaitTimeTracker:
    """Null object pattern for HumanWaitTimeTracker when tracking is not needed."""

    def start_wait(self) -> None:
        """No-op start_wait."""
        pass

    def end_wait(self) -> None:
        """No-op end_wait."""
        pass


class HumanInputCallbacksProvider:
    """Provide the list of human tools for a HumanToolsBase implementation.

    Provides two utilities:
    1. Ensures that function signatures / descriptions are never modified during override
       and exactly match the model's expected format.
    2. Ensures the list of provided human tools exactly matches the model's expectation.
    """

    def __init__(self, human_input_callbacks: HumanInputCallbacksBase):
        self._human_input_callbacks = human_input_callbacks
        # Use null object pattern - always have a tracker (null or real)
        self._wait_time_tracker: HumanWaitTimeTracker | _NullWaitTimeTracker = _NullWaitTimeTracker()

    def set_wait_time_tracker(self, tracker: HumanWaitTimeTracker) -> None:
        """Set the wait time tracker for this act execution.

        Args:
            tracker: The HumanWaitTimeTracker instance to use for tracking wait times.
        """
        self._wait_time_tracker = tracker

    # NOTE: The Nova Act model has been trained with the following tool description.
    #  Any modification may cause the tool to no longer function properly
    @final
    @tool(
        name="human_Approve",
        description=(
            "Use this tool to request human approval to complete tasks such as financial transactions, cart "
            "checkout or sensitive form submissions when the task requires it."
        ),
    )
    def approve(self, message: str) -> str:
        """
        Request human approval to complete particular tasks.

        Args:
            message: clear instructions to the human on what needs to be approved
        """
        # Track wait time around the blocking callback
        self._wait_time_tracker.start_wait()
        try:
            result = self._human_input_callbacks.approve(message)
            if result == ApprovalResponse.YES:
                return str(result.value)
            raise ApproveCanceledError()
        finally:
            self._wait_time_tracker.end_wait()

    # NOTE: The Nova Act model has been trained with the following tool description.
    #  Any modification may cause the tool to no longer function properly
    @final
    @tool(
        name="human_UiTakeover",
        description=(
            "Use this tool to request the human to take over the UI to complete a step, such as logging in, "
            "captcha, or filling sensitive information."
        ),
    )
    def ui_takeover(self, message: str) -> str:
        """
        Request human takeover for UI interactions.

        Args:
            message: clear instructions on what actions need to be completed by the human
        """
        # Track wait time around the blocking callback
        self._wait_time_tracker.start_wait()
        try:
            result = self._human_input_callbacks.ui_takeover(message)
            if result == UiTakeoverResponse.COMPLETE:
                return str(result.value)
            raise UiTakeoverCanceledError()
        finally:
            self._wait_time_tracker.end_wait()

    @final
    def provide(self) -> list[ActionType]:
        """Provide tools for a HumanInputCallbackProvider."""
        return [self.ui_takeover, self.approve]


class ApprovalResponse(Enum):
    YES = "yes"
    CANCEL = "cancel"


class UiTakeoverResponse(Enum):
    COMPLETE = "complete"
    CANCEL = "cancel"


class HumanInputCallbacksBase(ABC):
    """An abstract base class for providing human in the loop tools."""

    _human_input_callbacks_provider: HumanInputCallbacksProvider | None = None

    def __init__(self) -> None:
        self._act_session_id: str | None = None
        self._current_act_id: str | None = None
        self._most_recent_screenshot: str | None = None

    @property
    def most_recent_screenshot(self) -> str | None:
        """
        Get the most recent screenshot from the browser.

        This property provides access to the base64-encoded screenshot captured
        during the most recent step of Act execution. The screenshot is automatically
        updated by the dispatcher before each model step and can be used by human
        input callbacks to provide visual context when requesting human intervention.

        Returns:
            str: Base64-encoded screenshot image of the current browser state

        Example:
            def ui_takeover(self, message: str) -> None:
                screenshot = self.most_recent_screenshot
                display_to_human(screenshot, message)
        """
        return self._most_recent_screenshot

    @most_recent_screenshot.setter
    def most_recent_screenshot(self, most_recent_screenshot: str) -> None:
        """
        Set the most recent screenshot from the browser.

        This setter is called automatically by the ActDispatcher during each step
        to update the screenshot with the latest browser state. This ensures human
        input callbacks always have access to current visual context.

        Args:
            most_recent_screenshot: Base64-encoded screenshot image to store
        """
        self._most_recent_screenshot = most_recent_screenshot

    @property
    def act_session_id(self) -> str:
        assert self._act_session_id is not None, "act_session_id should be set after initializing the callback provider"
        return self._act_session_id

    @act_session_id.setter
    def act_session_id(self, act_session_id: str) -> None:
        """
        Initialize the provider with act session id.
        Can only be set once.

        Args:
            act_session_id: The session ID for the current Act session

        Raises:
            AssertionError: If act_session_id is already set
        """
        assert self._act_session_id is None, "act_session_id can only be set once"
        self._act_session_id = act_session_id

    @property
    def current_act_id(self) -> str:
        assert self._current_act_id is not None, "current_act_id from the Act session is not set"
        return self._current_act_id

    @current_act_id.setter
    def current_act_id(self, current_act_id: str) -> None:
        """
        Set the current act ID.

        Args:
            current_act_id: The current act ID
        """
        self._current_act_id = current_act_id

    @property
    def provider(self) -> HumanInputCallbacksProvider:
        """Provide HumanInputCallbacks as Tools."""
        if self._human_input_callbacks_provider is None:
            self._human_input_callbacks_provider = HumanInputCallbacksProvider(self)
        return self._human_input_callbacks_provider

    @final
    def as_tools(self) -> list[ActionType]:
        """
        List all tools provided by the HumanToolsBase class.
        """
        return self.provider.provide()

    @abstractmethod
    def approve(self, message: str) -> ApprovalResponse:
        pass

    @abstractmethod
    def ui_takeover(self, message: str) -> UiTakeoverResponse:
        pass


class DefaultHumanInputCallbacks(HumanInputCallbacksBase):
    """
    Default implementation of HumanInputCallbacksBase that raises an exception.

    This implementation is used when no custom human input provider is configured.
    It raises NoHumanInputToolAvailable for all human tools.
    """

    def __init__(self) -> None:
        """Initialize the default human input callbacks provider."""
        super().__init__()

    def approve(self, message: str) -> ApprovalResponse:
        raise NoHumanInputToolAvailable(message)

    def ui_takeover(self, message: str) -> UiTakeoverResponse:
        raise NoHumanInputToolAvailable(message)
