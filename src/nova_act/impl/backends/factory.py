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
from enum import Enum
from typing import Optional, TypeVar, Union

from nova_act.impl.backends.base import Endpoints
from nova_act.impl.backends.starburst.backend import StarburstBackend
from nova_act.impl.backends.sunburst.backend import SunburstBackend
from nova_act.impl.backends.sunshine import SunshineBackend
from nova_act.types.errors import AuthError
from nova_act.types.workflow import Workflow
from nova_act.util.logging import create_warning_box, make_trace_logger

_TRACE_LOGGER = make_trace_logger()

# TypeVar for Backend that can work with any Endpoints subtype
T = TypeVar("T", bound=Endpoints)

# Type alias for any concrete backend type that can be returned by the factory
NovaActBackend = Union[
    StarburstBackend,
    SunburstBackend,
    SunshineBackend,
]


class AuthStrategy(Enum):
    """Enumeration of supported authentication strategies."""

    API_KEY = "api_key"


class BackendFactory:
    """Factory for creating Backend instances based on parameters."""

    @staticmethod
    def create_backend(
        # auth strategies
        api_key: str | None = None,
        workflow: Workflow | None = None,
    ) -> NovaActBackend:
        """Create appropriate Backend instance with endpoints selection."""

        if workflow is not None:
            return workflow.backend

        auth_strategy = BackendFactory._determine_auth_strategy(
            api_key,
        )

        match auth_strategy:

            case AuthStrategy.API_KEY:
                assert api_key is not None  # Type narrowing

                return SunburstBackend(
                    api_key=api_key,
                )

    @staticmethod
    def _determine_auth_strategy(
        api_key: Optional[str],
    ) -> AuthStrategy:
        """Validate auth parameters and determine strategy."""
        provided_auths = [
            (api_key is not None, AuthStrategy.API_KEY),
        ]

        active_auths = [strategy for is_provided, strategy in provided_auths if is_provided]

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
            strategies = [strategy.value for strategy in active_auths]
            raise AuthError(f"Only one auth strategy allowed, got: {strategies}")

        strategy = active_auths[0]


        return strategy
