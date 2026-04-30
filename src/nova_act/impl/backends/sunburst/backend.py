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

from nova_act.impl.backends.burst.backend import BurstBackend
from nova_act.impl.backends.sunburst.client import SunburstClient

DEFAULT_WORKFLOW_DEFN_NAME: Final[str] = "default"


class SunburstBackend(BurstBackend[SunburstClient]):
    def __init__(
        self,
        api_key: str,
    ) -> None:
        self._api_key = api_key

        self._client = SunburstClient(
            api_key,
        )
        super().__init__()

    def get_auth_warning_message_for_backend(self, message: str) -> str:
        return self._client.get_auth_warning_message(message)

    def validate_auth(self) -> None:
        self._client.validate_api_key(self._api_key)
