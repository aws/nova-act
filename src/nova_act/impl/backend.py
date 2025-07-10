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
from dataclasses import dataclass
from enum import Enum


class Backend(Enum):
    PROD = "prod"


@dataclass
class BackendInfo:
    api_uri: str
    keygen_uri: str




URLS_BY_BACKEND = {
    Backend.PROD: BackendInfo(
        "https://nova.amazon.com/agent",
        "https://nova.amazon.com/act",
    ),
}




def get_urls_for_backend(backend: Backend) -> BackendInfo:
    return URLS_BY_BACKEND[backend]


def is_backend_info_for_backend(backend: Backend, backend_info: BackendInfo) -> bool:
    """Checks if the provided BackendInfo matches the provided Backend."""
    return backend_info == get_urls_for_backend(backend)


