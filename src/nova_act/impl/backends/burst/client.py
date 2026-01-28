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
from typing import Literal

from nova_act.impl.backends.burst.types import (
    CreateActRequest,
    CreateActResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    CreateWorkflowRunRequest,
    CreateWorkflowRunResponse,
    InvokeActStepRequest,
    InvokeActStepResponse,
    UpdateActRequest,
    UpdateActResponse,
    UpdateWorkflowRunRequest,
    UpdateWorkflowRunResponse,
)
from nova_act.types.act_result import ActGetResult
from nova_act.types.errors import NovaActError
from nova_act.types.state.act import Act


class BurstClient(ABC):
    @abstractmethod
    def create_act(self, request: CreateActRequest) -> CreateActResponse:
        """Create an act with type-safe request/response."""

    @abstractmethod
    def create_session(self, request: CreateSessionRequest) -> CreateSessionResponse:
        """Create a session with type-safe request/response."""

    @abstractmethod
    def create_workflow_run(self, request: CreateWorkflowRunRequest) -> CreateWorkflowRunResponse:
        """Create a workflow run with type-safe request/response."""

    @abstractmethod
    def invoke_act_step(self, request: InvokeActStepRequest) -> InvokeActStepResponse:
        """Invoke an act step with type-safe request/response."""

    @abstractmethod
    def update_act(self, request: UpdateActRequest) -> UpdateActResponse:
        """Update an act with type-safe request/response."""

    @abstractmethod
    def update_workflow_run(self, request: UpdateWorkflowRunRequest) -> UpdateWorkflowRunResponse:
        """Update a workflow run with type-safe request/response."""

    def send_act_telemetry(self, act: Act, success: ActGetResult | None, error: NovaActError | None) -> None:
        """Send telemetry for an act. By default, do not send any."""

    def send_environment_telemetry(self, session_id: str, actuator_type: Literal["custom", "playwright"]) -> None:
        """Send environment telemetry. By default, do not send any."""
