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
from playwright.sync_api import Page

from nova_act.types.guardrail import GuardrailCallable
from nova_act.util.url import validate_url


def go_to_url(
    url: str, page: Page, allowed_file_open_paths: list[str] = [], state_guardrail: GuardrailCallable | None = None
) -> None:

    # Navigate to the URL, after validating
    page.goto(
        validate_url(
            url=url,
            default_to_https=True,
            allowed_file_open_paths=allowed_file_open_paths,
            state_guardrail=state_guardrail,
        )
    )
