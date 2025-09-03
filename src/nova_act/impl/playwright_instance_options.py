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

from playwright.sync_api import Playwright

_DEFAULT_GO_TO_URL_TIMEOUT = 60


@dataclass
class PlaywrightInstanceOptions:
    maybe_playwright: Playwright | None
    starting_page: str
    chrome_channel: str
    headless: bool
    user_data_dir: str
    profile_directory: str | None
    cdp_endpoint_url: str | None
    screen_width: int
    screen_height: int
    user_agent: str | None
    record_video: bool
    ignore_https_errors: bool
    use_default_chrome_browser: bool = False
    go_to_url_timeout: int | None = None
    cdp_headers: dict[str, str] | None = None
    proxy: dict[str, str] | None = None

    def __post_init__(self) -> None:
        self.owns_playwright = self.maybe_playwright is None
        self.owns_context = self.cdp_endpoint_url is None and not self.use_default_chrome_browser
        self.go_to_url_timeout = 1000 * (self.go_to_url_timeout or _DEFAULT_GO_TO_URL_TIMEOUT)
