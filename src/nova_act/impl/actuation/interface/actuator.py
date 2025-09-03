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
from abc import ABC, abstractmethod
from typing import Any, Callable, Sequence

from deprecated import deprecated
from strands import tool
from strands.tools.decorator import DecoratedFunctionTool


@deprecated(version="2.0.200", reason="the `@action` decorator is no longer required.")
def action(method: Callable[..., Any]) -> Callable[..., Any]:
    """Annotate a method as an Action."""
    return tool(method)


class ActuatorBase(ABC):
    """Base class for defining an Actuator.

    Users provide Actions to their Actuator by implementing the `list_actions`
    method, which must return a `Sequence` of strands `DecoratedFunctionTools`.
    A `DecoratedFunctionTool` can be created by using strands's `@tool` decorator
    on a function/method. Once the user has provided this list of Actions, NovaAct
    parses the Action name, description, and signature from these and provides the
    information to the planning model.

    Actuators may also define the `domain` attribute. This is optional;
    when provided, it is used to ground the planning model to the specifics
    of the actuation environment.

    Actuators may also define custom `start` and `stop` methods, to be called
    when NovaAct enters and exits. Applications might include starting and
    stopping a required server or client; for example, an MCP ClientSession.

    """

    domain: str | None = None
    """An optional description of the actuation domain."""

    def start(self, **kwargs: Any) -> None:
        """Prepare for actuation."""

    def stop(self, **kwargs: Any) -> None:
        """Clean up when done."""

    @property
    @abstractmethod
    def started(self, **kwargs: Any) -> bool:
        """
        Tells whether the actuator instance was started or not.
        """

    @abstractmethod
    def list_actions(self) -> Sequence[DecoratedFunctionTool[..., Any]]:
        """List the valid Actions this Actuator can take."""

    def asdict(self) -> dict[str, Any]:
        """Return a dictionary representation of this class."""
        return {
            "domain": self.domain,
            "actions": [action.tool_spec for action in self.list_actions()],
        }
