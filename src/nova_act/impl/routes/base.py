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

from abc import ABC, abstractmethod

from nova_act.impl.backend import BackendInfo
from nova_act.tools.browser.interface.browser import BrowserObservation
from nova_act.types.state.act import Act
from nova_act.types.state.step import Step
from nova_act.util.logging import make_trace_logger

_TRACE_LOGGER = make_trace_logger()

DEFAULT_REQUEST_CONNECT_TIMEOUT = 30  # 30s
DEFAULT_REQUEST_READ_TIMEOUT = 5 * 60  # 5min


class Routes(ABC):
    """
    Routes class for Nova Act SDK.

    This class is responsible for:
    1. Routing requests to the appropriate backend
    2. Processing responses from the service
    3. Handling errors and exceptions
    """

    @abstractmethod
    def step(
        self, act: Act, observation: BrowserObservation, error_executing_previous_step: Exception | None = None
    ) -> Step:
        """Make a step request and handle errors."""

    def __init__(self, backend_info: BackendInfo):
        self.backend_info = backend_info
