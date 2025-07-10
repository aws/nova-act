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
from abc import ABC
from typing import Callable, Sequence

from strands import tool

NOVA_ACTION = "__nova_action__"


def action(method: Callable) -> Callable:
    """Annotate a method as an Action."""
    setattr(method, NOVA_ACTION, True)
    return tool(method)


class ActuatorBase(ABC):
    """Base class for defining an Actuator.

    Users provide Actions for their Actuator by annotating instance methods
    with the `@action` decorator. The `list_actions` method provides these
    Actions to NovaAct as a sequence of Callables; NovaAct will infer the
    Action name, description, and signature from these and provide the
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

    def start(self, **kwargs) -> None:
        """Prepare for actuation."""

    def stop(self, **kwargs) -> None:
        """Clean up when done."""

    def list_actions(self) -> Sequence[Callable]:
        """List the valid Actions this Actuator can take."""
        return list(
            filter(
                lambda method: hasattr(method, NOVA_ACTION),
                map(lambda method_name: getattr(self, method_name), dir(self)),
            )
        )

    def asdict(self):
        """Return a dictionary representation of this class."""
        # TODO: implement
        return {"domain": self.domain, "actions": [action.TOOL_SPEC for action in self.list_actions()]}
