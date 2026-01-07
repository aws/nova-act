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
from typing import Literal, Mapping, Type, cast

from boto3 import Session
from playwright.sync_api import Page, Playwright

from nova_act.impl.backends.burst.types import ActErrorData
from nova_act.impl.backends.starburst.backend import StarburstBackend
from nova_act.impl.backends.sunburst.backend import SunburstBackend
from nova_act.impl.common import rsync_to_temp_dir
from nova_act.impl.controller import NovaStateController
from nova_act.impl.dispatcher import ActDispatcher
from nova_act.impl.extension import ExtensionActuator
from nova_act.impl.inputs import (
    validate_base_parameters,
    validate_length,
    validate_prompt,
    validate_step_limit,
    validate_timeout,
)
from nova_act.impl.run_info_compiler import RunInfoCompiler
from nova_act.impl.telemetry import send_act_telemetry, send_environment_telemetry
from nova_act.tools.actuator.interface.actuator import ActionType
from nova_act.tools.browser.default.default_nova_local_browser_actuator import (
    DefaultNovaLocalBrowserActuator,
)
from nova_act.tools.browser.default.playwright_instance_options import (
    PlaywrightInstanceOptions,
)
from nova_act.tools.browser.interface.browser import BrowserActuatorBase
from nova_act.tools.browser.interface.playwright_pages import PlaywrightPageManagerBase
from nova_act.tools.human.interface.human_input_callback import (
    DefaultHumanInputCallbacks,
    HumanInputCallbacksBase,
)


from nova_act.impl.backends.factory import BackendFactory
from nova_act.types.act_errors import ActError, ActInvalidModelGenerationError
from nova_act.types.act_result import ActGetResult, ActResult
from nova_act.types.api.status import ActStatus
from nova_act.types.errors import (
    AuthError,
    ClientNotStarted,
    NovaActError,
    StartFailed,
    StopFailed,
    ValidationFailed,
)
from nova_act.types.events import EventType, LogType
from nova_act.types.features import PreviewFeatures, SecurityOptions
from nova_act.types.guardrail import GuardrailCallable
from nova_act.types.hooks import StopHook
from nova_act.types.json_type import JSONType
from nova_act.types.state.act import Act
from nova_act.types.workflow import Workflow, get_current_workflow
from nova_act.types.workflow_run import WorkflowRun
from nova_act.util.decode_string import decode_awl_raw_program
from nova_act.util.error_messages import get_missing_workflow_definition_error, get_no_authentication_error
from nova_act.util.event_handler import EventHandler
from nova_act.util.jsonschema import (
    STRING_SCHEMA,
    add_schema_to_prompt,
    populate_json_schema_response,
    validate_jsonschema_schema,
)
from nova_act.util.logging import (
    get_session_id_prefix,
    make_trace_logger,
    set_logging_session,
    setup_logging,
    trace_log_lines,
)
from nova_act.util.url import validate_url

DEFAULT_SCREEN_WIDTH = 1600
DEFAULT_SCREEN_HEIGHT = 900

_LOGGER = setup_logging(__name__)
_TRACE_LOGGER = make_trace_logger()


ManagedActuatorType = Type[DefaultNovaLocalBrowserActuator | ExtensionActuator]


class NovaAct:
    """Client for interacting with the Nova Act Agent.

    Example:
    ```
    >>> from nova_act import NovaAct
    >>> n = NovaAct(starting_page="https://nova.amazon.com/act/gym/next-dot/search")
    >>> n.start()
    >>> n.act("Find flights from Boston to Wolf on Feb 22nd")
    ```

    Attributes
    ----------
    started: bool
        whether the browser has been launched
    page : playwright.Page
        The playwright Page object for actuation
    pages: list[playwright.Page]
        All playwright Pages available in Browser
    dispatcher: Dispatcher
        Component for sending act prompts to the Browser

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
        starting_page: str | None = None,
        *,
        cdp_endpoint_url: str | None = None,
        cdp_headers: dict[str, str] | None = None,
        cdp_use_existing_page: bool = False,
        chrome_channel: str | None = None,
        clone_user_data_dir: bool = True,
        actuator: ManagedActuatorType | BrowserActuatorBase = DefaultNovaLocalBrowserActuator,
        go_to_url_timeout: int | None = None,
        headless: bool = False,
        ignore_https_errors: bool = False,
        security_options: SecurityOptions | None = None,
        logs_directory: str | None = None,
        nova_act_api_key: str | None = None,
        playwright_instance: Playwright | None = None,
        preview: PreviewFeatures | None = None,
        profile_directory: str | None = None,
        proxy: dict[str, str] | None = None,
        record_video: bool = False,
        screen_width: int = DEFAULT_SCREEN_WIDTH,
        screen_height: int = DEFAULT_SCREEN_HEIGHT,
        ignore_screen_dims_check: bool = False,
        state_guardrail: GuardrailCallable | None = None,
        stop_hooks: list[StopHook] = [],
        tty: bool = True,
        use_default_chrome_browser: bool = False,
        user_agent: str | None = None,
        user_data_dir: str | None = None,
        human_input_callbacks: HumanInputCallbacksBase | None = None,
        tools: list[ActionType] | None = None,
        workflow: Workflow | None = None,
    ):
        """Initialize a client object.

        Parameters
        ----------
        starting_page : str
            Starting web page for the browser window. Can be omitted if re-using an existing CDP page.
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
        actuator: ManagedActuatorType
            Type or instance of a custom actuator.
            Note that deviations from NovaAct's standard observation and I/O formats may impact model performance
        profile_directory: str
            Name of the Chrome user profile. Only needed if using an existing, non-Default Chrome profile.
            Must be relative path within user_data_dir.
        screen_width: int
            Width of the screen for the playwright instance. This sets the window size, while the dimensions of
            screenshots taken on the page will be the slightly smaller viewport size. Note that changing the default
            might impact agent performance.
        screen_height: int
            Height of the screen for the playwright instance. This sets the window size, while the dimensions of
            screenshots taken on the page will be the slightly smaller viewport size. Note that changing the default
            might impact agent performance.
        ignore_screen_dims_check: bool
            By default, NovaAct will fail to act if screen width/height outside of the acceptable range are provided.
            Pass this flag to warn instead.
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
        tty: bool
            By default, NovaAct listens for ctrl+x signals from the terminal, allowing users to exit agent action
            while keeping the browser session open (ctrl+c will kill the browser). The feature requires an
            additional listener thread, so this variable allows users to disable the feature where a tty is not
            available. Defaults to True. NOVA_ACT_DISABLE_TTY environment variable takes precedence over this value.
        cdp_endpoint_url: str, optional
            A Chrome DevTools Protocol (CDP) endpoint to connect to
        cdp_headers: dict[str, str], optional
            Additional HTTP headers to be sent when connecting to a CDP endpoint
        cdp_use_existing_page: bool
             If True, Nova Act will re-use an existing page from the CDP context rather
             than opening a new one
        user_agent: str, optional
            Optionally override the user agent used by playwright.
        logs_directory: str, optional
            Output directory for video and agent run output. Will default to a temp dir.
        record_video: bool
            Whether to record video
        go_to_url_timeout : int, optional
            Max wait time on initial page load in seconds
        ignore_https_errors: bool
            If True, ignore certificate validation errors for https urls. Defaults to False.
        state_guardrail: GuardrailCallable, optional
            A callback function that takes a GuardrailInputState and returns a GuardrailDecision.
            Called after taking an observation but before invoking step on the backend.
            If it returns GuardrailDecision.BLOCK, act() will raise ActGuardrailsError.
            If it returns GuardrailDecision.PASS or is not set, execution continues normally.
        stop_hooks: list[StopHook]
            A list of stop hooks that are called when this object is stopped.
        use_default_chrome_browser: bool
            Use the locally installed Chrome browser. Only works on MacOS.
        preview: PreviewFeatures
            Optional preview features for opt-in.
        security_options: SecurityOptions, optional
            Set of security-related parameters that overwrite default agent behavior
            allowed_file_open_paths: list[str]
                List of filepaths that the browser is allowed to navigate to as file:// urls.
                Defaults to [], which disallows the file:// url scheme.
            allowed_file_upload_paths: list[str]
                List of filepaths from which file uploads are permitted. Defaults to [], disabling all file uploads.
        proxy: dict[str, str], optional
            Proxy configuration for the browser. Should contain 'server', 'username', and 'password' keys.
        human_input_callbacks: HumanInputCallbacksBase | None = None
            An implementation of human input callbacks. If not provided, a request for human input tool will not be
            made.
        tools: list[ActionType] | None = None,
            A list of client provided tools.
        """
        self._workflow_run: WorkflowRun | None = None

        # initialize with default values if not specified by client
        if not security_options:
            security_options = SecurityOptions()


        self._workflow: Workflow | None = None
        self._set_workflow(workflow)

        self._run_info_compiler: RunInfoCompiler | None = None
        self._starting_page = starting_page
        self._state_guardrail = state_guardrail


        if preview is not None:
            _LOGGER.warning(
                "No preview features in this release! Check back soon!\n\n"
                "• If you are looking for Playwright Actuation, it is now the default, so no parameters are needed!\n"
                "• If you are looking for Custom Actuators, they can now be passed directly in the `actuator` param."
            )
            if not actuator and (custom_actuator := preview.get("custom_actuator")):
                actuator = cast(BrowserActuatorBase, custom_actuator)

        if actuator is ExtensionActuator:
            _LOGGER.warning(
                "`ExtensionActuator` is deprecated and no longer has any effect. Falling back to default behavior."
            )
            actuator = DefaultNovaLocalBrowserActuator

        _chrome_channel = str(chrome_channel or os.environ.get("NOVA_ACT_CHROME_CHANNEL", "chrome"))
        _headless = headless or bool(os.environ.get("NOVA_ACT_HEADLESS"))

        self._nova_act_api_key = nova_act_api_key or os.environ.get("NOVA_ACT_API_KEY")

        self._validate_authentication(scripted_api_key=nova_act_api_key)

        self._backend = BackendFactory.create_backend(
            api_key=self._nova_act_api_key,
            workflow=self._workflow,
        )

        # For SunburstBackend without an explicit workflow, create a default one
        # This centralizes workflow_run creation/update in Workflow.__enter__/__exit__
        if isinstance(self._backend, SunburstBackend) and self._workflow is None:
            self._workflow = Workflow(
                model_id="nova-act-latest",
                nova_act_api_key=self._nova_act_api_key,
            )
            self._workflow._managed = True

        validate_base_parameters(
            starting_page=self._starting_page,
            use_existing_page=bool(cdp_endpoint_url and cdp_use_existing_page),
            backend_url=self._backend.endpoints.api_url,
            profile_directory=profile_directory,
            user_data_dir=user_data_dir,
            screen_width=screen_width,
            screen_height=screen_height,
            logs_directory=logs_directory,
            chrome_channel=_chrome_channel,
            ignore_https_errors=ignore_https_errors,
            allowed_file_open_paths=security_options.allowed_file_open_paths,
            clone_user_data_dir=clone_user_data_dir,
            use_default_chrome_browser=use_default_chrome_browser,
            proxy=proxy,
            state_guardrail=state_guardrail,
            ignore_screen_dims_check=ignore_screen_dims_check,
        )

        self._session_user_data_dir_is_temp: bool = False
        if user_data_dir:  # pragma: no cover
            if clone_user_data_dir:
                # We want to make a copy so the original is unmodified.
                _LOGGER.info(f"Copying {user_data_dir} to temp dir")
                self._session_user_data_dir = rsync_to_temp_dir(user_data_dir)
                _LOGGER.info(f"Copied {user_data_dir} to {self._session_user_data_dir}")
                self._session_user_data_dir_is_temp = True
            else:
                # We want to just use the original.
                self._session_user_data_dir = user_data_dir
        else:
            # We weren't given an existing user_data_dir, just make a temp directory.
            self._session_user_data_dir = tempfile.mkdtemp(suffix="_nova_act_user_data_dir")
            self._session_user_data_dir_is_temp = True

        _LOGGER.debug(f"{self._session_user_data_dir=}")

        if logs_directory is None:
            logs_directory = tempfile.mkdtemp(suffix="_nova_act_logs")

        self._logs_directory = logs_directory
        self._session_logs_directory: str = ""
        if go_to_url_timeout is not None:
            validate_timeout(go_to_url_timeout)
        self.go_to_url_timeout = go_to_url_timeout


        validate_length(
            starting_page=self._starting_page,
            profile_directory=profile_directory,
            user_data_dir=self._session_user_data_dir,
            cdp_endpoint_url=cdp_endpoint_url,
            user_agent=user_agent,
            logs_directory=logs_directory,
        )

        self._tty = tty and not os.environ.get("NOVA_ACT_DISABLE_TTY")
        if self._tty and "PYTEST_CURRENT_TEST" in os.environ:
            _LOGGER.warning(
                "We noticed you are running NovaAct in a pytest runtime with `tty=True`! "
                "For improved performance, we recommend `tty=False.` "
                "If this is intended (e.g. you have terminal access and want to use ctrl+x "
                "to cancel `act` calls), then you may ignore this warning."
            )

        self.screen_width = screen_width
        self.screen_height = screen_height
        self.ignore_screen_dims_check = ignore_screen_dims_check

        self._stop_hooks = stop_hooks
        self._log_stop_hooks_registration()
        user_browser_args = os.environ.get("NOVA_ACT_BROWSER_ARGS", "").split()

        self._session_id: str | None = None

        # Session-level time tracking
        self._session_total_time_worked_s: float = 0.0
        self._session_total_human_wait_s: float = 0.0
        self._session_act_count: int = 0


        playwright_options = PlaywrightInstanceOptions(
            maybe_playwright=playwright_instance,
            starting_page=self._starting_page,
            chrome_channel=_chrome_channel,
            headless=_headless,
            user_data_dir=self._session_user_data_dir,
            profile_directory=profile_directory,
            cdp_endpoint_url=cdp_endpoint_url,
            screen_width=self.screen_width,
            screen_height=self.screen_height,
            user_agent=user_agent,
            record_video=bool(record_video and self._logs_directory),
            ignore_https_errors=ignore_https_errors,
            go_to_url_timeout=self.go_to_url_timeout,
            use_default_chrome_browser=use_default_chrome_browser,
            cdp_headers=cdp_headers,
            proxy=proxy,
            cdp_use_existing_page=cdp_use_existing_page,
            user_browser_args=user_browser_args,
            security_options=security_options,
        )
        self._cdp_endpoint_url = cdp_endpoint_url
        self._allowed_file_open_paths = security_options.allowed_file_open_paths

        self._actuator: BrowserActuatorBase
        self._dispatcher: ActDispatcher

        self._event_callback = None

        self._event_handler = EventHandler(self._event_callback)
        self._controller = NovaStateController(self._tty)

        if isinstance(actuator, type):
            if issubclass(actuator, DefaultNovaLocalBrowserActuator):
                if actuator is not DefaultNovaLocalBrowserActuator:
                    _LOGGER.warning(
                        f"Using a custom actuator: {actuator.__name__}\n"
                        "Deviations from NovaAct's standard observation"
                        " and I/O formats may impact model performance"
                    )
                _LOGGER.debug(f"Using a DefaultNovaLocalBrowserActuator: {actuator.__name__}")
                self._actuator = actuator(
                    playwright_options=playwright_options,
                    state_guardrail=state_guardrail,
                )
            else:
                raise ValidationFailed(
                    "Please subclass DefaultNovaLocalBrowserActuator if passing a custom actuator by type"
                )
        else:
            _LOGGER.warning(
                f"Using a user-defined actuator instance: {type(actuator).__name__}\n"
                "Deviations from NovaAct's standard observation and I/O formats may impact model performance"
            )
            self._actuator = actuator

        self._tools: list[ActionType] = tools or []
        self._human_input_callbacks = human_input_callbacks or self._get_default_human_input_callbacks()

        self._dispatcher = ActDispatcher(
            actuator=self._actuator,
            backend=self._backend,
            event_handler=self._event_handler,
            controller=self._controller,
            human_input_callbacks=self._human_input_callbacks,
            tools=self._tools,
            state_guardrail=state_guardrail,
        )


    def _validate_authentication(self, scripted_api_key: str | None) -> None:
        """Validate authentication configuration for NovaAct without Workflow.

        When a Workflow is used, authentication is validated by Workflow._initialize_backend
        before NovaAct is instantiated, so we can skip validation here.

        For NovaAct usage without Workflow, we validate:
        - At least one auth method exists (API key or AWS credentials)
        - AWS credentials alone require a Workflow
        - Warn when both API key and AWS credentials are present

        Args:
            scripted_api_key: The API key parameter passed to __init__

        Raises:
            AuthError: If no authentication method is available
            ValueError: If AWS credentials are present but workflow is missing
        """


        has_aws_credentials = Session().get_credentials() is not None
        has_api_key = self._nova_act_api_key is not None
        has_workflow = self._workflow is not None
        has_env_api_key = scripted_api_key is None and os.environ.get("NOVA_ACT_API_KEY") is not None

        # Workflow authentication is already validated in Workflow._initialize_backend
        if has_workflow:
            return

        # No authentication credentials at all
        if not has_api_key and not has_aws_credentials:
            raise AuthError(get_no_authentication_error())

        # AWS credentials require a Workflow construct
        if has_aws_credentials and not has_api_key:
            raise ValueError(get_missing_workflow_definition_error())

        # Warn when API key takes precedence over AWS credentials
        if has_env_api_key and has_aws_credentials:
            _LOGGER.warning(
                "Note: Using nova.amazon.com free version API Key from "
                "environment variable 'NOVA_ACT_API_KEY'. Ignoring AWS Credentials."
            )

    def _set_workflow(self, workflow: Workflow | None) -> None:
        if workflow is None:
            workflow = get_current_workflow()

        workflow_run: WorkflowRun | None = None
        if workflow is not None:
            if workflow.workflow_run is None:
                raise ValidationFailed(
                    "Workflow does not have workflow run set. Please use Workflow as a context manager"
                )
            workflow_run = workflow.workflow_run

        self._workflow = workflow
        self._workflow_run = workflow_run

    def _get_default_human_input_callbacks(self) -> HumanInputCallbacksBase:
        """Get the default HumanInputCallbacks implementation."""


        return DefaultHumanInputCallbacks()

    def _log_stop_hooks_registration(self) -> None:
        """Log registered stop hooks for debugging purposes."""
        if self._stop_hooks:
            hook_names = [type(hook).__name__ for hook in self._stop_hooks]
            _LOGGER.info(f"Registered stop hooks: {', '.join(hook_names)}")
        else:
            _LOGGER.debug("No stop hooks registered")

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
        if not self.started:
            _LOGGER.warning("Attention: Client is already stopped.")
            return
        self._stop(exc_type=exc_type)

    @property
    def started(self) -> bool:
        return self._actuator.started and self._session_id is not None

    @property
    def page(self) -> Page:
        """Get the current playwright page, if the provided actuator is of type PlaywrightPageManagerBase.

        This is the Playwright Page on which the SDK is currently actuating

        To get a specific page, use `NovaAct.pages` to list all pages,
        then fetch the intended page with its 0-starting index in `NovaAct.get_page(i)`.
        """
        return self.get_page()

    def get_page(self, index: int = -1) -> Page:
        """Get a particular playwright page by index or the currently actuating page if index == -1.

        Note: the order of these pages might not reflect their tab order in the window if they have been moved.

        Only available if the provided actuator is of type PlaywrightPageManagerBase.
        """
        if not self.started:
            raise ClientNotStarted("Run start() to start the client before accessing the Playwright Page.")

        if not isinstance(self._actuator, PlaywrightPageManagerBase):
            raise ValidationFailed(
                "Did you implement a non-playwright actuator? If so, you must get your own page object directly.\n"
                "If you are using playwright, ensure you are implementing PlaywrightPageManagerBase to get page access"
            )

        maybe_playwright_page = self._actuator.get_page(index)
        return maybe_playwright_page

    @property
    def pages(self) -> list[Page]:
        """Get the current playwright pages.

        Note: the order of these pages might not reflect their tab order in the window if they have been moved.

        Only available if the provided actuator is of type PlaywrightPageManagerBase.
        """
        if not self.started:
            raise ClientNotStarted("Run start() to start the client before accessing Playwright Pages.")

        if not isinstance(self._actuator, PlaywrightPageManagerBase):
            raise ValidationFailed(
                "Did you implement a non-playwright actuator? If so, you must get your own page object directly.\n"
                "If you are using playwright, ensure you are implementing PlaywrightPageManagerBase to get page access"
            )

        maybe_playwright_pages = self._actuator.pages
        return maybe_playwright_pages

    def go_to_url(self, url: str) -> None:
        """Navigates to the specified URL and waits for the page to settle."""

        validate_url(url, allowed_file_open_paths=self._allowed_file_open_paths, state_guardrail=self._state_guardrail)

        if not self.started or self._session_id is None:
            raise ClientNotStarted("Run start() to start the client before running go_to_url")

        self._actuator.go_to_url(url)
        self._actuator.wait_for_page_to_settle()

    @property
    def dispatcher(self) -> ActDispatcher:
        """Get an ActDispatcher for actuation on the current page."""
        if not self.started:
            raise ClientNotStarted("Client must be started before accessing the dispatcher.")
        assert self._dispatcher is not None
        return self._dispatcher

    def get_session_id(self) -> str:
        """Get the session ID for the current client.

        Raises ClientNotStarted if the client has not been started.
        """
        if not self.started:
            raise ClientNotStarted("Client must be started before accessing the session ID.")
        return str(self._session_id)

    def get_logs_directory(self) -> str:
        """Get the logs directory for the current client."""
        if not self._logs_directory:
            raise ValueError("Logs directory is not set.")

        return self._logs_directory

    def _init_session_logs_directory(self, base_dir: str, session_id: str) -> str:
        _session_logs_directory: str = os.path.join(base_dir, session_id) if base_dir else ""
        if _session_logs_directory:
            try:
                os.mkdir(_session_logs_directory)
            except Exception as e:
                _LOGGER.error(
                    f"Failed to create directory: {_session_logs_directory} with Error: {e} "
                    f"of type {type(e).__name__}"
                )
        return _session_logs_directory

    def get_session_logs_directory(self) -> str:
        """
        Get the session logs directory path where run_info_compiler.py creates files.

        Returns:
            str: Path to the session logs directory

        Raises:
            ValueError: If logs directory is not set
        """
        if not self._session_logs_directory:
            raise ValueError("Session logs directory is not set.")

        return self._session_logs_directory

    def start(self) -> None:
        """Start the client."""
        if self.started:
            _LOGGER.warning("Attention: Client is already started; to start over, run stop().")
            return


        try:
            # Enter workflow context if we manage it
            # This calls Workflow.__enter__() which creates the workflow_run
            if self._workflow is not None and self._workflow._managed:
                self._workflow.__enter__()
                self._workflow_run = self._workflow.workflow_run
            self._session_id = self._backend.create_session(self._workflow_run)

            self._human_input_callbacks.act_session_id = self._session_id

            set_logging_session(self._session_id)
            self._session_logs_directory = self._init_session_logs_directory(self._logs_directory, self._session_id)

            actuator_type: Literal["custom", "playwright"]
            actuator_type = "playwright" if isinstance(self._actuator, DefaultNovaLocalBrowserActuator) else "custom"

            send_environment_telemetry(
                endpoint=self._backend.endpoints.api_url,
                nova_act_api_key=self._nova_act_api_key,
                session_id=self._session_id,
                actuator_type=actuator_type,
            )

            self._actuator.start(starting_page=self._starting_page, session_logs_directory=self._session_logs_directory)

            self._run_info_compiler = RunInfoCompiler(self._session_logs_directory)
            session_logs_str = f" logs dir {self._session_logs_directory}" if self._session_logs_directory else ""

            loggable_url = self._starting_page or self._cdp_endpoint_url
            _TRACE_LOGGER.info(f"\nstart session {self._session_id} on {loggable_url}{session_logs_str}\n")
            self._event_handler.send_event(
                type=EventType.LOG,
                log_level=LogType.INFO,
                data=f"start session {self._session_id} on {loggable_url}{session_logs_str}",
            )

        except Exception as e:
            _LOGGER.exception(f"Failed to start the actuator: {e}")
            self._stop()
            raise StartFailed(str(e)) from e

    def register_stop_hook(self, hook: StopHook) -> None:
        """Register a stop hook that will be called during stop().

        Parameters
        ----------
        hook : StopHook
            The stop hook to register. Must implement the StopHook protocol.
        """
        if hook in self._stop_hooks:
            raise ValueError(f"Stop hook {hook} is already registered.")
        self._stop_hooks.append(hook)

    def unregister_stop_hook(self, hook: StopHook) -> None:
        """Unregister a previously registered stop hook.

        Parameters
        ----------
        hook : StopHook
            The stop hook to unregister.
        """
        if hook not in self._stop_hooks:
            raise ValueError(f"Stop hook {hook} is not registered.")
        self._stop_hooks.remove(hook)

    def _execute_stop_hooks(self) -> None:
        """Call all registered stop hooks."""
        for hook in self._stop_hooks:
            try:
                hook.on_stop(self)
            except Exception as e:
                _LOGGER.error(f"Error in stop hook {hook}: {e}", exc_info=True)

    def _stop(self, exc_type: Type[BaseException] | None = None) -> None:
        try:
            self._execute_stop_hooks()
            self._dispatcher.cancel_prompt()
            self._actuator.stop()

            # Log session-level time worked summary
            if self._session_act_count > 0 and self._session_total_time_worked_s > 0:
                from nova_act.types.act_metadata import _format_duration

                time_worked_str = _format_duration(self._session_total_time_worked_s)
                act_calls_text = "act call" if self._session_act_count == 1 else "act calls"

                if self._session_total_human_wait_s > 0:
                    human_wait_str = _format_duration(self._session_total_human_wait_s)
                    session_summary = (
                        f"⏱️  Approx. Total Time Worked in Session: {time_worked_str} "
                        f"across {self._session_act_count} {act_calls_text} "
                        f"(excluding {human_wait_str} human wait)"
                    )
                else:
                    session_summary = (
                        f"⏱️  Approx. Total Time Worked in Session: {time_worked_str} "
                        f"across {self._session_act_count} {act_calls_text}"
                    )

                trace_log_lines(session_summary)

                # Write session summary to JSON file
                if self._run_info_compiler and self._session_id:
                    self._run_info_compiler.write_session_summary(
                        session_id=self._session_id,
                        total_time_worked_s=self._session_total_time_worked_s,
                        total_human_wait_s=self._session_total_human_wait_s,
                        act_count=self._session_act_count,
                    )

            _TRACE_LOGGER.info(f"\nend session: {self._session_id}\n")
            self._event_handler.send_event(
                type=EventType.LOG, log_level=LogType.INFO, data=f"end session: {self._session_id}"
            )

            self._session_id = None
            set_logging_session(None)

            # Exit workflow context if we manage it
            # This calls Workflow.__exit__() which updates the workflow_run status
            if self._workflow is not None and self._workflow._managed:
                self._workflow.__exit__(exc_type, None, None)
        except Exception as e:
            raise StopFailed(str(e)) from e

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
        max_steps: int | None = None,
        model_temperature: float | None = None,
        model_top_k: int | None = None,
        model_seed: int | None = None,
        observation_delay_ms: int | None = None,
        schema: Mapping[str, JSONType] | None = None,
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
        observation_delay_ms: int | None
            Additional delay in milliseconds before taking an observation of the page
        schema: Dict[str, Any] | None
            .. deprecated::
                Use :meth:`act_get` instead for structured responses.
            An optional jsonschema, which the output should to adhere to

        Returns
        -------
        ActResult

        Raises
        ------
        ActError
        ValidationFailed
        """
        result = self._act(
            prompt=prompt,
            timeout=timeout,
            max_steps=max_steps,
            schema=schema,
            model_temperature=model_temperature,
            model_top_k=model_top_k,
            model_seed=model_seed,
            observation_delay_ms=observation_delay_ms,
        )

        if schema:
            # schema is deprecated but allow duck-typing to preserve backward compatibility.
            return result
        else:
            # Return the response-erased base result type.
            return result.without_response()

    def act_get(
        self,
        prompt: str,
        schema: Mapping[str, JSONType] = STRING_SCHEMA,
        *,
        timeout: int | None = None,
        max_steps: int | None = None,
        model_temperature: float | None = None,
        model_top_k: int | None = None,
        model_seed: int | None = None,
        observation_delay_ms: int | None = None,
    ) -> ActGetResult:
        """Actuate on the web browser using natural language, and return a structured response.

        This method is nearly identical to `act`, except it always provides the model with a
        JSONSchema for properly formatting responses. It should be used only when the user desires
        an answer from the model.

        For example, one would use `act_get` as follows, because a structured extract is requested:
        ```
        with NovaAct(...) as nova:
            result = nova.act_get("How many colors do you see on this page?", schema={"type": "integer"})
            print(result.parsed_response)
        ```

        In contrast, one would not use `act_get` for an example as follows, because no information is
        requested beyond the exit status of the call:
        ```
        with NovaAct(...) as nova:
            nova.act("Click on the 'Learn More' button.")
        ```

        Parameters
        ----------
        prompt: str
            The natural language task to actuate on the web browser.
        timeout: int, optional
            The timeout (in seconds) for the task to actuate.
        max_steps: int
            Configure the maximum number of steps (browser actuations) `act()` will take before giving up on the task.
            Use this to make sure the agent doesn't get stuck forever trying different paths. Default is 30.
        schema: Dict[str, Any]
            An optional jsonschema, which the output should to adhere to. This defaults to {"type": "string} when not
            specified.
        observation_delay_ms: int | None
            Additional delay in milliseconds before taking an observation of the page

        Returns
        -------
        ActResult

        Raises
        ------
        ActError
        ValidationFailed

        """
        return self._act(
            prompt=prompt,
            timeout=timeout,
            max_steps=max_steps,
            schema=schema,
            model_temperature=model_temperature,
            model_top_k=model_top_k,
            model_seed=model_seed,
            observation_delay_ms=observation_delay_ms,
        )

    def _act(
        self,
        prompt: str,
        timeout: int | None,
        max_steps: int | None,
        schema: Mapping[str, JSONType] | None,
        model_temperature: float | None,
        model_top_k: int | None,
        model_seed: int | None,
        observation_delay_ms: int | None,
    ) -> ActGetResult:
        """Shared logic for act() (with/without structured extract)."""
        if not self.started:
            raise ClientNotStarted("Run start() to start the client before calling act().")

        validate_timeout(timeout)
        validate_prompt(prompt)
        validate_step_limit(max_steps)

        if schema:
            validate_jsonschema_schema(schema)
            prompt = add_schema_to_prompt(prompt, schema)


        tools: list[ActionType] | None = None
        tools = self._tools.copy()
        if not isinstance(self._human_input_callbacks, DefaultHumanInputCallbacks):
            tools += self._human_input_callbacks.as_tools()

        assert self._session_id is not None, "Session ID should not be None when client is started"
        act_id = self._backend.create_act(self._workflow_run, self._session_id, prompt, tools)

        act = Act(
            id=act_id,
            prompt=prompt,
            session_id=str(self._session_id),
            timeout=timeout or float("inf"),
            max_steps=max_steps,
            model_temperature=model_temperature,
            model_top_k=model_top_k,
            model_seed=model_seed,
            observation_delay_ms=observation_delay_ms,
            workflow_run=self._workflow_run,
            ignore_screen_dims_check=self.ignore_screen_dims_check,
        )
        trace_log_lines(decode_awl_raw_program(f'act("{prompt}")'))

        self._event_handler.set_act(act)
        self._event_handler.send_event(type=EventType.LOG, log_level=LogType.INFO, data=f'act("{prompt}")')

        self._human_input_callbacks.current_act_id = act.metadata.act_id

        error: NovaActError | None = None
        result: ActGetResult | None = None

        try:
            result = self.dispatcher.dispatch(act)

            if schema:
                result = populate_json_schema_response(result, schema)
                if not result.matches_schema:
                    raise ActInvalidModelGenerationError(
                        message=f"Result '{result.response}' did not match expected schema '{schema}.'",
                        metadata=result.metadata,
                    )
        except (ActError, AuthError) as e:
            error = e
            raise e
        except Exception as e:
            error = ActError(metadata=act.metadata, message=f"{type(e).__name__}: {e}")
            raise error from e
        finally:
            send_act_telemetry(
                endpoint=self._backend.endpoints.api_url,
                nova_act_api_key=self._nova_act_api_key,
                act=act,
                success=result,
                error=error,
            )

            if self._run_info_compiler:
                file_path = self._run_info_compiler.compile(act, result)
                _TRACE_LOGGER.info(f"\n{get_session_id_prefix()}** View your act run here: {file_path}\n")
                self._event_handler.send_event(
                    type=EventType.LOG,
                    log_level=LogType.INFO,
                    data=f"** View your act run here: {file_path}",
                )

            # Update act status based on execution result on Finally
            if isinstance(self._backend, (StarburstBackend, SunburstBackend)):
                # Determine status based on execution outcome
                status: ActStatus
                error_data: ActErrorData | None = None
                if error is not None:
                    status = "FAILED"
                    error_data = ActErrorData(message=str(error), type=type(error).__name__)
                else:
                    status = "SUCCEEDED"

                if self._workflow_run is not None:
                    self._backend.update_act(
                        workflow_run=self._workflow_run,
                        session_id=act.session_id,
                        act_id=act.id,
                        status=status,
                        error=error_data,
                    )
                else:
                    # This should not happen since we check for workflow_run earlier
                    raise ValueError("StarburstBackend requires workflow context for update_act")

        # Update session-level time tracking
        if result and result.metadata.time_worked_s is not None:
            self._session_total_time_worked_s += result.metadata.time_worked_s
            self._session_total_human_wait_s += result.metadata.human_wait_time_s
            self._session_act_count += 1

        return result

