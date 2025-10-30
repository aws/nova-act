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

import boto3

from nova_act.impl.backends.base import Endpoints
from nova_act.impl.backends.helios import HeliosBackend
from nova_act.impl.backends.sunshine import SunshineBackend
from nova_act.types.errors import (
    AuthError,
)
from nova_act.util.logging import create_warning_box, make_trace_logger

_TRACE_LOGGER = make_trace_logger()

# TypeVar for Backend that can work with any Endpoints subtype
T = TypeVar("T", bound=Endpoints)

# Type alias for any concrete backend type that can be returned by the factory
NovaActBackend = Union[
    HeliosBackend,
    SunshineBackend,
]


class AuthStrategy(Enum):
    """Enumeration of supported authentication strategies."""

    BOTO_SESSION = "boto_session"
    API_KEY = "api_key"


class BackendFactory:
    """Factory for creating Backend instances based on parameters."""

    @staticmethod
    def create_backend(
        # auth strategies
        api_key: str | None = None,
        boto_session: boto3.Session | None = None,
    ) -> NovaActBackend:
        """Create appropriate Backend instance with endpoints selection."""


        auth_strategy = BackendFactory._determine_auth_strategy(
            boto_session,
            api_key,
        )

        match auth_strategy:

            case AuthStrategy.BOTO_SESSION:
                assert boto_session is not None  # Type narrowing

                return HeliosBackend(
                    boto_session=boto_session,
                )

            case AuthStrategy.API_KEY:
                assert api_key is not None  # Type narrowing
                return SunshineBackend(
                    api_key=api_key,
                )

    @staticmethod
    def _determine_auth_strategy(
        boto_session: Optional[boto3.Session],
        api_key: Optional[str],
    ) -> AuthStrategy:
        """Validate auth parameters and determine strategy."""
        provided_auths = [
            (boto_session is not None, AuthStrategy.BOTO_SESSION),
            (api_key is not None, AuthStrategy.API_KEY),
        ]

        active_auths = [strategy for is_provided, strategy in provided_auths if is_provided]

        if len(active_auths) == 0:
            # We show the default message asking to get API key if no auth strategy provided
            _message = create_warning_box(
                [
                    "Authentication failed.",
                    "",
                    f"Please ensure you are using a key from: {SunshineBackend.get_default_endpoints().keygen_url}",
                ]
            )
            raise AuthError(_message)
        elif len(active_auths) > 1:
            strategies = [strategy.value for strategy in active_auths]
            raise AuthError(f"Only one auth strategy allowed, got: {strategies}")

        strategy = active_auths[0]


        return strategy
