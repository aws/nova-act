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
from typing import Any

from nova_act.types.act_errors import ActError
from nova_act.types.act_result import ActResult
from nova_act.types.state.act import Act


class ActDispatcher(ABC):

    @abstractmethod
    def dispatch_and_wait_for_prompt_completion(self, act: Act) -> ActResult | ActError:
        pass

    @abstractmethod
    def wait_for_page_to_settle(self, session_id: str, timeout: int | None = None) -> None:
        pass

    @abstractmethod
    def go_to_url(self, url: str, session_id: str, timeout: int | None = None) -> None:
        pass

    @abstractmethod
    def cancel_prompt(self, act: Act | None = None) -> Any:
        pass
