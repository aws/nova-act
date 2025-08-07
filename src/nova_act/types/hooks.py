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
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from nova_act.nova_act import NovaAct


class StopHook(Protocol):
    """Interface for exit hooks that can be registered with NovaAct.

    Exit hooks are called during the stop() method, allowing for custom cleanup
    or finalization logic to be executed when the NovaAct client is stopped.
    """

    def on_stop(self, nova_act: "NovaAct") -> None:
        """Called when NovaAct is stopping.

        Parameters
        ----------
        nova_act : NovaAct
            The NovaAct instance that is being stopped
        """
        ...
