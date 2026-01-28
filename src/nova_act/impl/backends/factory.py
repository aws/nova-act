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

from typing import NamedTuple, Optional, TypeVar, Union

from nova_act.impl.backends.base import Endpoints
from nova_act.impl.backends.starburst.backend import StarburstBackend
from nova_act.impl.backends.sunburst.backend import SunburstBackend
from nova_act.types.errors import AuthError
from nova_act.types.workflow import Workflow
from nova_act.util.logging import create_warning_box

# TypeVar for Backend that can work with any Endpoints subtype
T = TypeVar("T", bound=Endpoints)

# Type alias for any concrete backend type that can be returned by the factory
NovaActBackend = Union[
    StarburstBackend,
    SunburstBackend,
]


class BackendFactory:
    """Factory for creating Backend instances based on parameters."""

    class BackendResult(NamedTuple):
        backend: NovaActBackend
        workflow: Workflow | None

    @staticmethod
    def create_backend(
        # auth strategies
        api_key: str | None = None,
        workflow: Workflow | None = None,
    ) -> BackendFactory.BackendResult:
        """Create appropriate Backend instance with endpoints selection."""

        if workflow is not None:
            return BackendFactory.BackendResult(workflow.backend, workflow)

        BackendFactory._validate_auth(
            api_key,
        )


        # For non-StarburstBackends without an explicit workflow, create a default one
        # This centralizes workflow_run creation/update in Workflow.__enter__/__exit__
        workflow = Workflow(
            model_id="nova-act-preview",
            nova_act_api_key=api_key,
        )
        workflow._managed = True

        return BackendFactory.BackendResult(workflow.backend, workflow)

    @staticmethod
    def _validate_auth(
        api_key: Optional[str],
    ) -> None:
        """Validate auth parameters."""
        provided_auths = [
            (api_key is not None, "api_key"),
        ]

        active_auths = list(filter(lambda x: x[0], provided_auths))

        if len(active_auths) == 0:
            # We show the default message asking to get API key if no auth strategy provided
            _message = create_warning_box(
                [
                    "Authentication failed.",
                    "",
                    "Please ensure you are using a key from: https://nova.amazon.com/dev-apis",
                ]
            )
            raise AuthError(_message)
        elif len(active_auths) > 1:
            strategies = [strategy for _, strategy in active_auths]
            raise AuthError(f"Only one auth strategy allowed, got: {strategies}")
