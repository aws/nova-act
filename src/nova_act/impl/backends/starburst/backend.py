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
from boto3 import Session
from botocore.config import Config

from nova_act.impl.backends.base import Endpoints
from nova_act.impl.backends.burst.backend import BurstBackend
from nova_act.impl.backends.starburst.client import StarburstClient
from nova_act.types.errors import IAMAuthError
from nova_act.util.logging import setup_logging

_LOGGER = setup_logging(__name__)


class StarburstBackend(BurstBackend[Endpoints]):
    def __init__(
        self,
        boto_session: Session,
        backend_override: str | None = None,
        boto_config: Config | None = None,
    ):
        self._boto_session = boto_session
        self._boto_config = boto_config

        super().__init__(
        )

    def _create_client(self, endpoints: Endpoints) -> StarburstClient:
        return StarburstClient(endpoints, self._boto_session, self._boto_config)

    def validate_auth(self) -> None:
        self._validate_boto_session()

    def _validate_boto_session(self) -> None:
        """
        Validate that the boto3 session has valid credentials associated with a real IAM identity.

        Args:
            boto_session: The boto3 session to validate

        Raises:
            IAMAuthError: If the boto3 session doesn't have valid credentials or the credentials
                        are not associated with a real IAM identity
        """
        # Check if credentials exist
        try:
            credentials = self._boto_session.get_credentials()
            if not credentials:
                raise IAMAuthError("IAM credentials not found. Please ensure your boto3 session has valid credentials.")
        except Exception as e:
            raise IAMAuthError(f"Failed to get credentials from boto session: {str(e)}")

        # Verify credentials are associated with a real IAM identity
        try:
            sts_client = self._boto_session.client("sts")
            sts_client.get_caller_identity()
        except Exception as e:
            raise IAMAuthError(
                f"IAM validation failed: {str(e)}. Check your credentials with 'aws sts get-caller-identity'."
            )

    def get_auth_warning_message_for_backend(self, message: str) -> str:
        return message

    @classmethod
    def resolve_endpoints(
        cls,
        backend_stage: str | None = None,
        backend_api_url_override: str | None = None,
        local_port: int | None = None,
    ) -> Endpoints:
        api_url = "https://nova-act.us-east-1.amazonaws.com/"


        return Endpoints(api_url=api_url)
