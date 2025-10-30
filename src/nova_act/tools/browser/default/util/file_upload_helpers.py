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
from typing import Optional, Protocol

from playwright.sync_api import FileChooser, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


class _FileChooserInfo(Protocol):
    """
    What Playwright yields inside `with page.expect_file_chooser(...) as info:`.
    https://playwright.dev/python/docs/api/class-filechooser
    """

    value: FileChooser


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
    # Some tests may pass a simple Mock for `page` without the expect_file_chooser API.
    expect_file_chooser_function = getattr(page, "expect_file_chooser", None)
    if expect_file_chooser_function is None:
        page.mouse.click(x, y)
        return None

    try:
        context_manager = expect_file_chooser_function(timeout=timeout_ms)

        # If the expect file function returned something that isn't a context manager (e.g. in mocked tests)
        # also just click and bail out.
        is_context_manager = hasattr(context_manager, "__enter__") and hasattr(context_manager, "__exit__")
        if not is_context_manager:
            page.mouse.click(x, y)
            return None

        file_chooser_info: _FileChooserInfo
        with context_manager as file_chooser_info:
            # Perform the intended click exactly once while listening for the chooser.
            page.mouse.click(x, y)

        # If a file chooser shows up, return it (Playwright provides it at `info.value`)
        return file_chooser_info.value

    except (PlaywrightTimeoutError, AttributeError, TypeError):
        # Timeout => no chooser fired.
        # AttributeError/TypeError => likely a half-mocked page; treat as no chooser.
        return None
