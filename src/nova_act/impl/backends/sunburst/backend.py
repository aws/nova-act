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
from typing_extensions import Final

from nova_act.impl.backends.base import ApiKeyEndpoints
from nova_act.impl.backends.burst.backend import BurstBackend
from nova_act.impl.backends.sunburst.client import SunburstClient
from nova_act.types.errors import AuthError
from nova_act.util.logging import create_warning_box

DEFAULT_WORKFLOW_DEFN_NAME: Final[str] = "default"


class SunburstBackend(BurstBackend[ApiKeyEndpoints]):
    def __init__(
        self,
        api_key: str,
    ) -> None:
        self._api_key = api_key

        super().__init__(
        )

    def _create_client(self, endpoints: ApiKeyEndpoints) -> SunburstClient:
        return SunburstClient(endpoints, self._api_key)

    def get_auth_warning_message_for_backend(self, message: str) -> str:
        return create_warning_box([message, "", f"Please ensure you are using a key from: {self.endpoints.keygen_url}"])

    @classmethod
    def resolve_endpoints(
        cls,
    ) -> ApiKeyEndpoints:
        api_url = "https://api.nova.amazon.com"
        keygen_url = "https://nova.amazon.com/dev-apis"


        return ApiKeyEndpoints(api_url=api_url, keygen_url=keygen_url)

    def validate_auth(self) -> None:
        if len(self._api_key) != self.endpoints.valid_api_key_length:
            raise AuthError(self.get_auth_warning_message("Invalid API key length"))
