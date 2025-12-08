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
from typing import Optional

from playwright.sync_api import FileChooser, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


def click_and_maybe_return_file_chooser(
    page: Page,
    x: float,
    y: float,
    *,
    timeout_ms: int = 600,
) -> Optional[FileChooser]:
    """
    Perform a single *left click* at (x, y), wrapped in Playwright's `expect_file_chooser`.
    Returns the `FileChooser` if clicking opened a native file chooser dialog; otherwise returns None.

    Notes:
    This function does *not* complete/cancel the chooser. The caller decides what to do next.
    This is because there is no playwright API to easily cancel the chooser. One could call
    file_chooser.set_files([]) to "dismiss" the chooser, but pages often have some
    on-upload listener and this would trigger an update to the page's state.

    In order to prevent this side effect, we simply do nothing with the file chooser. This allows
    the agent to later upload the file with an agent type.
    However, because this file chooser is left open, for some sites, it also prevents any other action
    from being taken until a file has been uploaded.
    """
    try:
        with page.expect_file_chooser(timeout=timeout_ms) as file_chooser_info:
            page.mouse.click(x, y)

        # If a file chooser shows up, return it (Playwright provides it at `info.value`)
        return file_chooser_info.value
    except (PlaywrightTimeoutError, AttributeError, TypeError):
        # Timeout => no chooser fired.
        # AttributeError/TypeError => likely a half-mocked page; treat as no chooser.
        return None
