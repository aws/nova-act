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
from boto3.session import Session

from nova_act.impl.backend import Backend, get_urls_for_backend
from nova_act.impl.routes.base import Routes
from nova_act.impl.routes.helios import HeliosRoutes
from nova_act.impl.routes.sunshine import SunshineRoutes


def for_backend(
    backend: Backend,
    api_key: str,
    boto_session: Session | None = None,
) -> Routes:
    """Get a Routes implementation for a given Backend."""

    backend_info = get_urls_for_backend(backend)


    if backend in [
        Backend.HELIOS,
    ]:
        if boto_session is None:
            raise ValueError(backend_info, "boto_session cannot be None for the helios backend.")
        return HeliosRoutes(backend_info, boto_session)
    elif backend in [
        Backend.PROD,
    ]:
        return SunshineRoutes(backend_info, api_key)
    else:
        raise NotImplementedError(f"No Routes implementation for {backend}")
