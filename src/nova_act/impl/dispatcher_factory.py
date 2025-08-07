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
import boto3

from nova_act.impl.backend import BackendInfo
from nova_act.impl.custom_actuation.custom_dispatcher import CustomActDispatcher
from nova_act.impl.custom_actuation.interface.actuator import ActuatorBase
from nova_act.impl.dispatcher import ActDispatcher
from nova_act.impl.extension import ExtensionDispatcher
from nova_act.impl.playwright import PlaywrightInstanceManager


def create_act_dispatcher(
    playwright_manager: PlaywrightInstanceManager,
    nova_act_api_key: str | None,
    backend_info: BackendInfo,
    tty: bool,
    extension_path: str,
    boto_session: boto3.Session | None,
    actuator: ActuatorBase | None = None,
) -> ActDispatcher:
    """Create a dispatcher for actuation"""
    if actuator is not None:
        return CustomActDispatcher(
            nova_act_api_key=nova_act_api_key,
            backend_info=backend_info,
            actuator=actuator,
            tty=tty,
        )
    else:
        return ExtensionDispatcher(
            backend_info=backend_info,
            nova_act_api_key=nova_act_api_key,
            tty=tty,
            playwright_manager=playwright_manager,
            extension_path=extension_path,
            boto_session=boto_session,
        )
