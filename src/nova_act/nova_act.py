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
from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from typing import Any, Dict, Type, cast

from playwright.sync_api import Page, Playwright

from nova_act.impl.backend import Backend, get_urls_for_backend
from nova_act.impl.common import get_default_extension_path, get_extension_version
from nova_act.impl.extension import DEFAULT_ENDPOINT_NAME, ExtensionDispatcher
from nova_act.impl.inputs import (
    validate_base_parameters,
    validate_length,
    validate_prompt,
    validate_step_limit,
    validate_timeout,
    validate_url,
)
from nova_act.impl.playwright import PlaywrightInstanceManager
from nova_act.types.act_errors import ActError
from nova_act.types.act_result import ActResult
from nova_act.types.errors import AuthError, ClientNotStarted, StartFailed, StopFailed, ValidationFailed
from nova_act.types.state.act import Act
from nova_act.util.jsonschema import add_schema_to_prompt, populate_json_schema_response, validate_jsonschema_schema
from nova_act.util.logging import get_session_id_prefix, make_trace_logger, set_logging_session, setup_logging

DEFAULT_SCREEN_WIDTH = 1600
DEFAULT_SCREEN_HEIGHT = 900

DEFAULT_ACT_MAX_STEPS = 30

_LOGGER = setup_logging(__name__)
_TRACE_LOGGER = make_trace_logger()


class NovaAct:
    """Client for interacting with the Nova Act Agent.

    Example:
    ```
    >>> from nova_act import NovaAct
    >>> n = NovaAct(starting_page="https://www.amazon.com")
    >>> n.start()
    >>> n.act("search for a coffee maker")
    ```

    Attributes
    ----------
    started: bool
        whether the browser has been launched
    page : playwright.Page
        The playwright Page object for actuation
    pages: list[playwright.Page]
        All playwright Pages available in Browser
    dispatcher: ExtensionDispatcher
        Component for sending act prompts to the Chrome Extension

    Methods
    -------
    start()
        Starts the client
    act(command)
        Actuates a natural language command in the web browser
    stop()
        Stops the client
    get_page(i)
        Gets a specific playwright page by its index in the browser context
    """

    def __init__(
        self,
        starting_page: str,
        *,
        user_data_dir: str | None = None,
        clone_user_data_dir: bool = True,
        profile_directory: str | None = None,
        extension_path: str | None = None,
        screen_width: int = DEFAULT_SCREEN_WIDTH,
        screen_height: int = DEFAULT_SCREEN_HEIGHT,
        headless: bool = False,
        chrome_channel: str | None = None,
        nova_act_api_key: str | None = None,
        playwright_instance: Playwright | None = None,
        endpoint_name: str = DEFAULT_ENDPOINT_NAME,
        tty: bool = True,
        cdp_endpoint_url: str | None = None,
        user_agent: str | None = None,
        logs_directory: str | None = None,
        record_video: bool = False,
        go_to_url_timeout: int | None = None,
        ignore_https_errors: bool = False,
    ):
        """Initialize a client object.

        Parameters
        ----------
        starting_page : str
            Starting web page for the browser window
        user_data_dir: str, optional
            Path to Chrome data storage (cookies, cache, etc.).
            If not specified, will use a temp dir.
            Note that if multiple NovaAct instances are used in the same process (e.g., via a ThreadPool), each
            one must have its own user_data_dir. In practice, this means either not specifying user_data_dir
            (so a fresh temp dir is used for each instance) or using clone_user_data_dir=True.
        clone_user_data_dir: bool
            If True (default), will make a copy of user_data_dir into a temp dir for each instance of NovaAct.
            This ensures the original is not modified and that each instance has its own user_data_dir.
            If user_data_dir is not specified, this flag has no effect.
        profile_directory: str
            Directory for the Chrome user profile within user_data_dir. Only needed if using an existing Chrome profile.
        extension_path : str, optional
            Path to the compiled Chrome extension for browser actuation
        screen_width: int
            Width of the screen for the playwright instance. Within range [1536, 2304].
        screen_height: int
            Height of the screen for the playwright instance. Within range [864, 1296].
        headless: bool
            Whether to launch the Playwright browser in headless mode. Defaults to False. Can also be enabled with
            the `NOVA_ACT_HEADLESS` environment variable.
        chrome_channel: str, optional
            Browser channel to use (e.g., "chromium", "chrome-beta", "msedge" etc.). Defaults to "chrome". Can also
            be specified via `NOVA_ACT_CHROME_CHANNEL` environment variable.
        nova_act_api_key: str
            API key for interacting with NovaAct. Will override the NOVA_ACT_API_KEY environment variable
        playwright_instance: Playwright
            Add an existing Playwright instance for use
        endpoint_name: str
            The name of the inference endpoint to call for act() planning
        tty: bool
            Whether output logs should be formatted for a terminal (true) or file (false)
        cdp_endpoint_url: str, optional
            A CDP endpoint to connect to
        user_agent: str, optional
            Optionally override the user agent used by playwright.
        logs_directory: str, optional
            Output directory for video and agent run output. Will default to a temp dir.
        record_video: bool
            Whether to record video
        go_to_url_timeout : int, optional
            Max wait time on initial page load in seconds
        ignore_https_errors: bool
            Whether to ignore https errors for url to allow website with self-signed certificates
        """

        self._backend = Backend.PROD
        self._backend_info = get_urls_for_backend(self._backend)

        extension_path = extension_path or get_default_extension_path()
        self._extension_version = get_extension_version(extension_path)

        self._starting_page = starting_page or "https://www.google.com"

        if user_data_dir:  # pragma: no cover
            # We were supplied an existing user_data_dir.
            if clone_user_data_dir:
                # We want to make a copy so the original is unmodified.
                self._session_user_data_dir = tempfile.mkdtemp(suffix="_nova_act_user_data_dir")
                _LOGGER.debug(f"Copying {user_data_dir} to {self._session_user_data_dir=}")
                shutil.copytree(user_data_dir, self._session_user_data_dir, dirs_exist_ok=True)
                self._session_user_data_dir_is_temp = True
            else:
                # We want to just use the original.
                self._session_user_data_dir = user_data_dir
                self._session_user_data_dir_is_temp = False
        else:
            # We weren't given an existing user_data_dir, just make a temp directory.
            self._session_user_data_dir = tempfile.mkdtemp(suffix="_nova_act_user_data_dir")
            self._session_user_data_dir_is_temp = True

        _LOGGER.debug(f"{self._session_user_data_dir=}")

        if logs_directory is None:
            logs_directory = tempfile.mkdtemp(suffix="_nova_act_logs")

        self._logs_directory = logs_directory

        _chrome_channel = cast(str, chrome_channel or os.environ.get("NOVA_ACT_CHROME_CHANNEL", "chrome"))
        _headless = headless or bool(os.environ.get("NOVA_ACT_HEADLESS"))

        validate_base_parameters(
            extension_path=extension_path,
            starting_page=self._starting_page,
            backend_uri=self._backend_info.api_uri,
            profile_directory=profile_directory,
            user_data_dir=self._session_user_data_dir,
            screen_width=screen_width,
            screen_height=screen_height,
            logs_directory=logs_directory,
            chrome_channel=_chrome_channel,
            ignore_https_errors=ignore_https_errors,
        )
        if go_to_url_timeout is not None:
            validate_timeout(go_to_url_timeout)
        self.go_to_url_timeout = go_to_url_timeout

        nova_act_api_key = nova_act_api_key or os.environ.get("NOVA_ACT_API_KEY")

        if not nova_act_api_key:
            raise AuthError(backend_info=self._backend_info)
        self._nova_act_api_key = nova_act_api_key

        self.endpoint_name = endpoint_name

        validate_length(
            extension_path=extension_path,
            starting_page=self._starting_page,
            profile_directory=profile_directory,
            user_data_dir=self._session_user_data_dir,
            nova_act_api_key=self._nova_act_api_key,
            endpoint_name=self.endpoint_name,
            cdp_endpoint_url=cdp_endpoint_url,
            user_agent=user_agent,
            logs_directory=logs_directory,
            backend=self._backend,
        )
        self._tty = tty

        self.screen_width = screen_width
        self.screen_height = screen_height

        self._playwright = PlaywrightInstanceManager(
            maybe_playwright=playwright_instance,
            starting_page=self._starting_page,
            chrome_channel=_chrome_channel,
            headless=_headless,
            extension_path=extension_path,
            user_data_dir=self._session_user_data_dir,
            profile_directory=profile_directory,
            cdp_endpoint_url=cdp_endpoint_url,
            screen_width=self.screen_width,
            screen_height=self.screen_height,
            user_agent=user_agent,
            record_video=bool(record_video and self._logs_directory),
            ignore_https_errors=ignore_https_errors,
        )

        self._dispatcher: ExtensionDispatcher | None = None

    def __del__(self) -> None:
        if hasattr(self, "_session_user_data_dir_is_temp") and self._session_user_data_dir_is_temp:
            _LOGGER.debug(f"Deleting {self._session_user_data_dir}")
            shutil.rmtree(self._session_user_data_dir, ignore_errors=True)

    def __enter__(self) -> NovaAct:
        self.start()
        return self

    def __exit__(
        self, exc_type: Type[BaseException] | None, exc_value: BaseException | None, traceback: BaseException | None
    ) -> None:
        self.stop()

    @property
    def started(self) -> bool:
        """Check if the browser is started."""
        return self._playwright.started and self._dispatcher is not None

    @property
    def page(self) -> Page:
        """Get the current playwright page.

        This is the Playwright Page on which the SDK is currently actuating

        To get a specific page, use `NovaAct.pages` to list all pages,
        then fetch the intended page with its 0-starting index in `NovaAct.get_page(i)`
        """
        return self.get_page()

    def get_page(self, index: int = -1) -> Page:
        """Get a particular playwright page by index or the currently actuating page if index == -1.

        Note: the order of these pages might not reflect their tab order in the window if they have been moved
        """
        if not self.started:
            raise ClientNotStarted("Run start() to start the client before accessing the Playwright Page.")
        return self._playwright.get_page(index)

    @property
    def pages(self) -> list[Page]:
        """Get the current playwright pages.

        Note: the order of these pages might not reflect their tab order in the window if they have been moved
        """
        if not self.started:
            raise ClientNotStarted("Run start() to start the client before accessing Playwright Pages.")
        return self._playwright.context.pages

    @property
    def dispatcher(self) -> ExtensionDispatcher:
        """Get an ExtensionDispatcher for actuation on the current page."""
        if not self.started:
            raise ClientNotStarted("Client must be started before accessing the dispatcher.")
        assert self._dispatcher is not None
        return self._dispatcher

    def start(self) -> None:
        """Start the client."""
        if self.started:
            _LOGGER.warning("Attention: Client is already started; to start over, run stop().")
            return


        try:
            session_id = str(uuid.uuid4())
            set_logging_session(session_id)
            if self._logs_directory:
                session_logs_directory = os.path.join(self._logs_directory, session_id)
            else:
                session_logs_directory = ""

            if session_logs_directory:
                try:
                    os.mkdir(session_logs_directory)
                except Exception as e:
                    _LOGGER.error(
                        f"Failed to create directory: {session_logs_directory} with Error: {e} "
                        f"of type {type(e).__name__}"
                    )

            self._playwright.start(session_logs_directory)
            if self._dispatcher is None:
                self._dispatcher = ExtensionDispatcher(
                    backend_info=self._backend_info,
                    nova_act_api_key=self._nova_act_api_key,
                    tty=self._tty,
                    session_id=session_id,
                    playwright_manager=self._playwright,
                    extension_version=self._extension_version,
                    session_logs_directory=session_logs_directory,
                )
                set_logging_session(session_id)
            self._dispatcher.wait_for_page_to_settle(go_to_url_timeout=self.go_to_url_timeout)
            session_logs_str = f" logs dir {session_logs_directory}" if session_logs_directory else ""
            _TRACE_LOGGER.info(f"\nstart session {session_id} on {self._starting_page}{session_logs_str}\n")
        except Exception as e:
            self._stop()
            raise StartFailed from e

    def _stop(self) -> None:
        try:
            if self._dispatcher is not None:
                self._dispatcher.cancel_prompt()
            if self._playwright.started:
                self._playwright.stop()
            self._dispatcher = None
            _TRACE_LOGGER.info("\nend session\n")
            set_logging_session(None)
        except Exception as e:
            raise StopFailed from e

    def stop(self) -> None:
        """Stop the client."""
        if not self.started:
            _LOGGER.warning("Attention: Client is already stopped.")
            return
        self._stop()

    def act(
        self,
        prompt: str,
        *,
        timeout: int | None = None,
        max_steps: int = DEFAULT_ACT_MAX_STEPS,
        schema: Dict[str, Any] | None = None,
        endpoint_name: str | None = None,
        model_temperature: int | None = None,
        model_top_k: int | None = None,
        model_seed: int | None = None,
    ) -> ActResult:
        """Actuate on the web browser using natural language.

        Parameters
        ----------
        prompt: str
            The natural language task to actuate on the web browser.
        timeout: int, optional
            The timeout (in seconds) for the task to actuate.
        max_steps: int
            Configure the maximum number of steps (browser actuations) `act()` will take before giving up on the task.
            Use this to make sure the agent doesn't get stuck forever trying different paths. Default is 30.
        schema: Dict[str, Any] | None
            An optional jsonschema, which the output should to adhere to
        endpoint_name: str
            The name of the inference endpoint to call for act() planning

        Returns
        -------
        ActResult

        Raises
        ------
        ActError
        ValidationFailed
        """
        if not self.started:
            raise ClientNotStarted("Run start() to start the client before calling act().")

        validate_timeout(timeout)
        validate_prompt(prompt)
        validate_step_limit(max_steps)

        if endpoint_name is None:
            endpoint_name = self.endpoint_name

        if schema:
            validate_jsonschema_schema(schema)
            prompt = add_schema_to_prompt(prompt, schema)

        act = Act(
            prompt,
            session_id=self.dispatcher.session_id,
            endpoint_name=endpoint_name,
            timeout=timeout or float("inf"),
            max_steps=max_steps,
            model_temperature=model_temperature,
            model_top_k=model_top_k,
            model_seed=model_seed,
        )
        _TRACE_LOGGER.info(f'{get_session_id_prefix()}act("{prompt}")')

        try:
            response = self.dispatcher.dispatch_and_wait_for_prompt_completion(act)
            if isinstance(response, ActError):
                raise response
        except (ActError, AuthError):
            raise
        except Exception as e:
            raise ActError(metadata=act.metadata) from e

        if schema:
            response = populate_json_schema_response(response, schema)

        return response

    def go_to_url(self, url: str) -> None:
        """Navigates to the specified URL and waits for the page to settle."""

        validate_url(url, "go_to_url")

        if not self.page or not self.dispatcher:
            raise ClientNotStarted("Run start() to start the client before running go_to_url")

        self.page.goto(url, wait_until="domcontentloaded")
        self.page.wait_for_selector("#autonomy-listeners-registered", state="attached")
        self.dispatcher.wait_for_page_to_settle(go_to_url_timeout=self.go_to_url_timeout)
