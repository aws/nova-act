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
import json
from typing import Any, Dict, Optional

from playwright.sync_api import BrowserContext

from nova_act.impl.backend import URLS_BY_BACKEND, Backend
from nova_act.util.logging import setup_logging

_LOGGER = setup_logging(__name__)


class StepServerTimeTracker:
    _instance = None
    _initialized: bool

    def __new__(
        cls, browser_context: BrowserContext | None = None, endpoint_pattern: str = "/step"
    ) -> "StepServerTimeTracker":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, browser_context: BrowserContext | None = None, endpoint_pattern: str = "/step"):
        if self._initialized:
            return

        if browser_context is None:
            raise ValueError("First initialization requires browser_context")

        self.context = browser_context
        self.endpoint_pattern = endpoint_pattern
        self._step_durations: Dict[str, float] = {}
        self._setup_tracking()
        self._initialized = True

    def _setup_tracking(self) -> None:
        def handle_response(response: Any) -> None:
            if self.endpoint_pattern in response.url and response.request.post_data:
                try:
                    body = json.loads(response.request.post_data)
                    act_id = body.get("actId")
                    timing = response.request.timing
                    duration = (timing["responseStart"] - timing["requestStart"]) / 1000
                    if act_id:
                        key = f"{act_id}"
                        self._step_durations[key] = duration
                except Exception as e:
                    _LOGGER.debug("Missed step server timing", exc_info=e)

        self.context.on("response", handle_response)

    def get_step_duration_s(self, *, act_id: str) -> Optional[float]:
        key = f"{act_id}"
        return self._step_durations.get(key)

    @classmethod
    def get_instance(cls) -> Optional["StepServerTimeTracker"]:
        if cls._instance is not None:
            return cls._instance
        return None
