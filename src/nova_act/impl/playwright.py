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
import os
import subprocess
import time
from typing import Any

import requests
from install_playwright import install
from playwright.sync_api import BrowserContext
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

from nova_act.impl.common import should_install_chromium_dependencies
from nova_act.impl.playwright_instance_options import PlaywrightInstanceOptions
from nova_act.types.errors import (
    ClientNotStarted,
    InvalidPlaywrightState,
    PageNotFoundError,
    StartFailed,
    ValidationFailed,
)
from nova_act.util.common_js_expressions import Expressions
from nova_act.util.logging import setup_logging

_LOGGER = setup_logging(__name__)

_DEFAULT_USER_AGENT_SUFFIX = " Agent-NovaAct/0.9"
_MACOS_LOCAL_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
_CDP_PORT = 9222


class PlaywrightInstanceManager:
    """RAII Manager for the Playwright Browser"""

    def __init__(self, options: PlaywrightInstanceOptions):
        self._playwright = options.maybe_playwright
        self._owns_playwright = options.owns_playwright
        self._starting_page = options.starting_page
        self._chrome_channel = options.chrome_channel
        self._headless = options.headless
        self._user_data_dir = options.user_data_dir
        self._profile_directory = options.profile_directory
        self._cdp_endpoint_url = options.cdp_endpoint_url
        self._owns_context = options.owns_context
        self.screen_width = options.screen_width
        self.screen_height = options.screen_height
        self.user_agent = options.user_agent
        self._record_video = options.record_video
        self._ignore_https_errors = options.ignore_https_errors
        self._go_to_url_timeout = options.go_to_url_timeout
        self._use_default_chrome_browser = options.use_default_chrome_browser
        self._cdp_headers = options.cdp_headers
        self._proxy = options.proxy

        if self._cdp_endpoint_url is not None or self._use_default_chrome_browser:
            if self._record_video:
                raise ValidationFailed("Cannot record video when connecting over CDP")
            if self._profile_directory:
                raise ValidationFailed("Cannot specify a profile directory when connecting over CDP")
            if self._proxy:
                raise ValidationFailed("Cannot specify a proxy when connecting over CDP")

        self._context: BrowserContext | None = None
        self._launched_default_chrome_popen: subprocess.Popen[bytes] | None = None
        self._session_logs_directory: str | None = None

    @property
    def started(self) -> bool:
        """Check if the client is started."""
        return self._context is not None

    def _init_browser_context(self, context: BrowserContext, trusted_page: Page) -> Page:
        """Go to the starting page and exit."""

        first_page = context.new_page()
        first_page.goto(self._starting_page)
        trusted_page.close()
        return first_page

    def _launch_browser(self, context_options: Any) -> BrowserContext:
        """Launches a Playwright Chromium based browser with Chromium as fallback."""
        if self._playwright is None:
            raise ValueError("Playwright instance is not initialized")

        if (channel := context_options.get("channel")) != "chromium":
            try:
                context = self._playwright.chromium.launch_persistent_context(self._user_data_dir, **context_options)
                return context
            except PlaywrightError:
                _LOGGER.warning(
                    f"The Nova Act SDK is unable to run with `chrome_channel='{channel}'` and is "
                    "falling back to 'chromium'. If you wish to use an alternate `chrome_channel`, "
                    f"please install it with `python -m playwright install {channel}`. For more information, "
                    "please consult Playwright's documentation: https://playwright.dev/python/docs/browsers."
                )
                context_options["channel"] = "chromium"

        context = self._playwright.chromium.launch_persistent_context(
            self._user_data_dir,
            **context_options,
        )
        if self._go_to_url_timeout is not None:
            context.set_default_navigation_timeout(self._go_to_url_timeout)
        return context

    def start(self, session_logs_directory: str | None) -> None:
        """Start and attach the Browser"""
        if self._context is not None:
            _LOGGER.warning("Playwright already attached, to start over, stop the client")
            return

        if self._record_video:
            assert session_logs_directory is not None, "Started without a logs dir when record_video is True"

        self._session_logs_directory = session_logs_directory
        try:
            # Start a new playwright instance if one was not provided by the user
            if self._playwright is None:
                try:
                    self._playwright = sync_playwright().start()
                except RuntimeError as e:
                    if "It looks like you are using Playwright Sync API inside the asyncio loop" in str(e):
                        raise StartFailed(
                            "Each NovaAct must have its own execution context. "
                            "To parallelize, dedicate one thread per NovaAct instance."
                        ) from e
                    raise

            if self._use_default_chrome_browser:
                # Launch the default browser with a debug port and a freshly copied user data dir.

                _LOGGER.info("Quitting Chrome if it's running...")
                subprocess.run(["osascript", "-e", 'quit app "Google Chrome"'], check=True)

                # Wait for it to exit.
                exited = False
                for _ in range(6):  # Wait up to 3 seconds.
                    try:
                        output = subprocess.check_output(["pgrep", "-x", "Google Chrome"])
                        if output.strip():
                            time.sleep(0.5)
                            continue
                    except subprocess.CalledProcessError:
                        pass
                    exited = True
                    break

                assert exited, "Could not quit Chrome"

                # Start Chrome with a debug port and the new user data dir.
                _LOGGER.info(
                    f"Launching Chrome with user-data-dir={self._user_data_dir} remote-debugging-port={_CDP_PORT}"
                )
                self._launched_default_chrome_popen = subprocess.Popen(
                    [
                        _MACOS_LOCAL_CHROME_PATH,
                        f"--remote-debugging-port={_CDP_PORT}",
                        f"--user-data-dir={self._user_data_dir}",
                        f"--profile-directory={self._profile_directory if self._profile_directory else 'Default'}",
                        f"--window-size={self.screen_width},{self.screen_height}",
                        "--no-first-run",
                        *(["--headless=new"] if self._headless else []),
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                try:
                    # Wait until Chrome's debugger endpoint is available. When it is, set cdp_endpoint_url to it.
                    for _ in range(10):  # Wait up to 5 seconds.
                        try:
                            resp = requests.get(f"http://localhost:{_CDP_PORT}/json/version")
                            resp.raise_for_status()
                            ws_url = resp.json().get("webSocketDebuggerUrl")
                            if ws_url:
                                self._cdp_endpoint_url = ws_url
                        except requests.RequestException:
                            # Just retry.
                            pass
                        time.sleep(0.5)
                    assert self._cdp_endpoint_url is not None, "Could not get Chrome's debugger endpoint"
                except Exception:
                    self._launched_default_chrome_popen.terminate()
                    raise

                _LOGGER.info(f"Chrome launched with ws url {self._cdp_endpoint_url}")

            # Attach to a context or create one.
            if self._cdp_endpoint_url is not None:
                browser = self._playwright.chromium.connect_over_cdp(self._cdp_endpoint_url, headers=self._cdp_headers)

                if not browser.contexts:
                    raise InvalidPlaywrightState("No contexts found in the browser")
                context = browser.contexts[0]
                if self.user_agent:
                    context.set_extra_http_headers({"User-Agent": self.user_agent})
                trusted_page = context.new_page()


            else:
                if not os.environ.get("NOVA_ACT_SKIP_PLAYWRIGHT_INSTALL"):
                    with_deps = should_install_chromium_dependencies()
                    if not install(self._playwright.chromium, with_deps=with_deps):
                        raise StartFailed(
                            "Failed to install Playwright browser binaries. If you have "
                            "already installed these, you may skip this step by specifying the "
                            "NOVA_ACT_SKIP_PLAYWRIGHT_INSTALL environment variable. Otherwise, "
                            "the binaries can be installed with "
                            f"`python -m playwright install {'--with-deps ' if with_deps else ''}chromium`. "
                            "For more information, please consult Playwright's documentation: "
                            "https://playwright.dev/python/docs/browsers"
                        )

                user_browser_args = os.environ.get("NOVA_ACT_BROWSER_ARGS", "").split()

                launch_args = [
                    f"--window-size={self.screen_width},{self.screen_height}",
                    "--disable-blink-features=AutomationControlled",  # Suppress navigator.webdriver flag
                    *(["--headless=new"] if self._headless else []),
                    *([] if not self._profile_directory else [f"--profile-directory={self._profile_directory}"]),
                    "--silent-debugger-extension-api",
                    "--remote-allow-origins=https://chrome-devtools-frontend.appspot.com",
                    *user_browser_args,
                ]

                context_options = {
                    "headless": self._headless,
                    "args": launch_args,
                    "ignore_default_args": [
                        # Disable infobar with automated test software message
                        "--enable-automation",
                        # Overwrite Playwright default to hide scrollbars in headless mode
                        "--hide-scrollbars",
                    ],
                    # If you set viewport any user changes to the browser size will skew screenshots
                    "no_viewport": True,
                    "ignore_https_errors": self._ignore_https_errors,
                    "channel": self._chrome_channel,
                }
                if self._proxy:
                    context_options["proxy"] = self._proxy
                if self.user_agent:
                    context_options["user_agent"] = self.user_agent
                else:
                    # Detect user agent by launching a headless browser, and add suffix.
                    browser = self._playwright.chromium.launch(
                        headless=True, args=["--headless=new", *user_browser_args]
                    )
                    page = browser.new_page()
                    original_user_agent = page.evaluate(Expressions.GET_USER_AGENT.value)
                    browser.close()
                    # Replace the headless chrome bit since it's a detection artifact.
                    original_user_agent = original_user_agent.replace("HeadlessChrome/", "Chrome/")
                    context_options["user_agent"] = original_user_agent + _DEFAULT_USER_AGENT_SUFFIX


                if self._record_video:
                    assert self._session_logs_directory is not None
                    context_options["record_video_dir"] = self._session_logs_directory
                    context_options["record_video_size"] = {"width": self.screen_width, "height": self.screen_height}

                context = self._launch_browser(context_options)
                trusted_page = context.pages[0]

            self._init_browser_context(context, trusted_page)
            self._context = context

        except StartFailed:
            raise
        except Exception as e:
            _LOGGER.exception(f"Failed to start and initialize Playwright for NovaAct: {e}")
            self.stop()
            raise StartFailed("Failed to start and initialize Playwright for NovaAct") from e

    def stop(self) -> None:
        """Stop and detach the Browser"""
        if self._context is not None and self._record_video:
            for page in self._context.pages:
                if page.video:
                    video_path = page.video.path()
                    if video_path:
                        assert self._record_video
                        assert self._session_logs_directory is not None
                        page_index = self._context.pages.index(page)
                        new_path = os.path.join(
                            self._session_logs_directory,
                            f"session_video_tab-{page_index}.webm",
                        )
                        try:
                            os.rename(video_path, new_path)
                        except OSError as e:
                            _LOGGER.error(f"An Unexpected error occured when renaming {video_path}: {e}")

        if self._owns_context and self._context is not None:
            self._context.close()

        if self._launched_default_chrome_popen is not None:
            self._launched_default_chrome_popen.terminate()
            self._launched_default_chrome_popen = None

        # Stop playwright instance if one was created by us
        if self._owns_playwright and self._playwright is not None:
            self._playwright.stop()
            self._playwright = None

        self._context = None
        self._session_logs_directory = None

    @property
    def _active_page(self) -> Page:
        assert self._context is not None and len(self._context.pages) > 0
        return self._context.pages[-1]

    @property
    def main_page(self) -> Page:
        """Get an open page on which to send messages"""
        return self.get_page(-1)

    def get_page(self, index: int) -> Page:
        """Get an open page by its index in the browser context"""
        if self._context is None:
            raise ClientNotStarted("Playwright not attached, run start() to start")

        if index == -1:
            return self._active_page

        num_pages = len(self._context.pages)

        if num_pages < 1:
            raise InvalidPlaywrightState("No pages found in browser context.")

        if index <= (-1 * num_pages) or index >= num_pages:  # Allow backward indexing for convenience
            pages = [f"{i}: {page}" for i, page in enumerate(self._context.pages)]
            joined_output = "\n".join(pages)
            raise PageNotFoundError(f"Page with index {index} not found. Choose from:\n{joined_output}")

        return self._context.pages[index]

    @property
    def context(self) -> BrowserContext:
        """Get the browser context"""
        if self._context is None:
            raise ClientNotStarted("Playwright not attached, run start() to start")

        return self._context
