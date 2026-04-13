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
"""BrowserActions package — pure capability logic extracted from CLI commands.

Takes a NovaAct instance and exposes every browser capability as a method.
No Click, no output formatting, no logging — pure logic only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nova_act.cli.browser.services.browser_actions.exploration import ExplorationMixin
from nova_act.cli.browser.services.browser_actions.inspection import (
    ALL_PROPERTIES,
    DEFAULT_EVALUATE_TIMEOUT_SECONDS,
    InspectionMixin,
    is_complex_result,
    wrap_with_timeout,
)
from nova_act.cli.browser.services.browser_actions.interaction import InteractionMixin
from nova_act.cli.browser.services.browser_actions.navigation import NavigationMixin
from nova_act.cli.browser.services.browser_actions.tab_operations import TabOperationsMixin

if TYPE_CHECKING:
    from nova_act import NovaAct


class BrowserActions(NavigationMixin, ExplorationMixin, InteractionMixin, InspectionMixin, TabOperationsMixin):
    """Pure browser capability logic — no CLI, no output formatting, no logging."""

    def __init__(self, nova_act: NovaAct) -> None:
        self._nova_act = nova_act


__all__ = [
    "BrowserActions",
    "ALL_PROPERTIES",
    "DEFAULT_EVALUATE_TIMEOUT_SECONDS",
    "is_complex_result",
    "wrap_with_timeout",
]
