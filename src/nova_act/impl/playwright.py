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
from typing import cast

from install_playwright import install
from playwright.sync_api import BrowserContext
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, Playwright, Video, sync_playwright

from nova_act.impl.common import should_install_chromium_dependencies
from nova_act.impl.message_encrypter import MessageEncrypter
from nova_act.impl.window_messages import (
    ADD_COMPLETION_LISTENER_EXPRESSION,
    HANDLE_ENCRYPTED_MESSAGE_FUNCTION_NAME,
    POST_MESSAGE_EXPRESSION,
    WindowMessageHandler,
)
from nova_act.types.errors import (
    ClientNotStarted,
    InvalidPlaywrightState,
    PageNotFoundError,
    StartFailed,
    ValidationFailed,
)
from nova_act.util.logging import setup_logging

_LOGGER = setup_logging(__name__)

_DEFAULT_USER_AGENT_SUFFIX = " Agent-NovaAct/0.9"


class PlaywrightInstanceManager:
    """RAII Manager for the Playwright Browser"""

    def __init__(
        self,
        maybe_playwright: Playwright | None,
        starting_page: str,
        chrome_channel: str,
        headless: bool,
        extension_path: str,
        user_data_dir: str,
        profile_directory: str | None,
        cdp_endpoint_url: str | None,
        screen_width: int,
        screen_height: int,
        user_agent: str | None,
        record_video: bool,
        ignore_https_errors: bool,
    ):
        self._playwright = maybe_playwright
        self._owns_playwright = maybe_playwright is None  # Tracks if we created an instance
        self._starting_page = starting_page
        self._chrome_channel = chrome_channel
        self._headless = headless
        self._extension_path = extension_path
        self._user_data_dir = user_data_dir
        self._profile_directory = profile_directory
        self._cdp_endpoint_url = cdp_endpoint_url
        self._owns_context = cdp_endpoint_url is None
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.user_agent = user_agent
        self._record_video = record_video
        self._ignore_https_errors = ignore_https_errors

        if self._cdp_endpoint_url:
            if self._record_video:
                raise ValidationFailed("Cannot record video when connecting over CDP")
            if self._profile_directory:
                raise ValidationFailed("Cannot specify a profile directory when connecting over CDP")
            if self.user_agent:
                raise ValidationFailed("Cannot specify a user agent when connecting over CDP")

        self._context: BrowserContext | None = None
        self._session_logs_directory: str | None = None
        self._encrypter = MessageEncrypter()
        self._window_message_handler = WindowMessageHandler(self._encrypter)

    @property
    def encrypter(self) -> MessageEncrypter:
        """Get the encrypter."""
        return self._encrypter

    @property
    def window_message_handler(self):
        """Get the window message handler."""
        return self._window_message_handler

    @property
    def started(self):
        """Check if the client is started."""
        return self._context is not None

    def _init_browser_context(self, context: BrowserContext, trusted_page: Page) -> Page:
        # The protocol here is as follows:
        #
        # - Navigate a trusted page. Trusted here means it won't tamper with the content script.
        # - Wait for the page to register listeners.
        # - Send the encryption key through that page to the extension service worker.
        # - Service worker will then register the tab id with the SDK.
        # - Open the starting page and close the trusted page.

        context.expose_function(HANDLE_ENCRYPTED_MESSAGE_FUNCTION_NAME, self._window_message_handler.handle_message)

        # This will handle adding the message handler to all pages that gets created/navigated in the browser context.
        # This seems to be more robust than adding the listeners to each page via domcontentloaded
        context.add_init_script(f"({ADD_COMPLETION_LISTENER_EXPRESSION})();")

        # Send in the secret key through a trusted page.
        trusted_page.goto("https://nova.amazon.com/agent-loading")
        trusted_page.wait_for_selector("#autonomy-listeners-registered", state="attached")
        trusted_page.evaluate(POST_MESSAGE_EXPRESSION, self._encrypter.make_set_key_message())

        # The default opened page may contain infobars with messages while new pages should not.
        first_page = context.new_page()
        first_video_path = None
        if self._record_video:  # We will delete this video since we're closing this page
            first_video_path = cast(Video, trusted_page.video).path()
        trusted_page.close()

        # Navigate to the starting page, from the default (about:blank).
        first_page.goto(self._starting_page, wait_until="domcontentloaded")
        first_page.wait_for_selector("#autonomy-listeners-registered", state="attached")

        if first_video_path and os.path.exists(first_video_path):
            os.remove(first_video_path)

        return first_page

    def _launch_browser(self, context_options):
        """Launches a Playwright Chromium based browser with Chromium as fallback."""
        if (channel := context_options.get("channel")) != "chromium":
            try:
                context = self._playwright.chromium.launch_persistent_context(
                    self._user_data_dir, **context_options  # type: ignore[arg-type]
                )
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
            **context_options,  # type: ignore[arg-type]
        )
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

            # Attach to a context or create one.
            if self._cdp_endpoint_url is not None:
                browser = self._playwright.chromium.connect_over_cdp(self._cdp_endpoint_url)

                if not browser.contexts:
                    raise InvalidPlaywrightState("No contexts found in the browser")
                context = browser.contexts[0]
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
                    f"--disable-extensions-except={self._extension_path}",
                    f"--load-extension={self._extension_path}",
                    f"--window-size={self.screen_width},{self.screen_height}",
                    "--disable-blink-features=AutomationControlled",  # Suppress navigator.webdriver flag
                    *(["--headless=new"] if self._headless else []),
                    *([] if not self._profile_directory else [f"--profile-directory={self._profile_directory}"]),
                    "--silent-debugger-extension-api",
                    *user_browser_args,
                ]

                context_options = {
                    "headless": self._headless,
                    "args": launch_args,
                    "ignore_default_args": [
                        "--enable-automation"
                    ],  # Disable infobar with automated test software message
                    # If you set viewport any user changes to the browser size will skew screenshots
                    "no_viewport": True,
                    "ignore_https_errors": self._ignore_https_errors,
                    "channel": self._chrome_channel,
                }
                if self.user_agent:
                    context_options["user_agent"] = self.user_agent
                else:
                    # Detect user agent by launching a headless browser, and add suffix.
                    browser = self._playwright.chromium.launch(
                        headless=True, args=["--headless=new", *user_browser_args]
                    )
                    page = browser.new_page()
                    original_user_agent = page.evaluate("() => navigator.userAgent")
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

        # Stop playwright instance if one was created by us
        if self._owns_playwright and self._playwright is not None:
            self._playwright.stop()
            self._playwright = None

        self._context = None
        self._session_logs_directory = None

    @property
    def _active_page(self):
        assert self._context is not None and len(self._context.pages) > 0
        return self._context.pages[-1]

    @property
    def main_page(self):
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
        "Get the browser context"
        if self._context is None:
            raise ClientNotStarted("Playwright not attached, run start() to start")

        return self._context
