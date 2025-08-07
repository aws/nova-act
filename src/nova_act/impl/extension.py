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
import time
import uuid
from contextlib import nullcontext
from dataclasses import replace
from typing import Any, ContextManager, Dict, cast

from boto3.session import Session
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page
from retry.api import retry_call

from nova_act.__version__ import VERSION as SDK_VERSION
from nova_act.impl.backend import BackendInfo
from nova_act.impl.common import get_extension_version
from nova_act.impl.custom_actuation.interface.browser import BrowserActuatorBase, BrowserObservation, JSONSerializable
from nova_act.impl.custom_actuation.interface.playwright_pages import PlaywrightPageManagerBase
from nova_act.impl.dispatcher import ActDispatcher
from nova_act.impl.keyboard_event_watcher import KeyboardEventWatcher
from nova_act.impl.playwright import PlaywrightInstanceManager
from nova_act.impl.protocol import parse_errors
from nova_act.impl.window_messages import (
    CANCEL_PROMPT_TYPE,
    DISPATCH_PROMPT_TYPE,
    POST_MESSAGE_EXPRESSION,
    WAIT_FOR_PAGE_TO_SETTLE_PROMPT_TYPE,
)
from nova_act.types.act_errors import ActCanceledError, ActClientError, ActDispatchError, ActError
from nova_act.types.act_result import ActResult
from nova_act.types.errors import IAMAuthError
from nova_act.types.state.act import Act, ActCanceled, ActFailed, ActSucceeded
from nova_act.types.state.page import PageState
from nova_act.util.logging import (
    LoadScroller,
    get_session_id_prefix,
    is_quiet,
    make_trace_logger,
    setup_logging,
)
from nova_act.util.step_server_time_tracker import StepServerTimeTracker

# Check every 0.1 seconds, for a total of 30 seconds.
DEFAULT_POLL_SLEEP_S = 0.1
DEFAULT_TIMEOUT_S = 30.0

# Give Extension 30s to accept the request
EXTENSION_POLL_SLEEP_S = 0.1
EXTENSION_TIMEOUT_S = 30.0
MAX_WAIT_FOR_PAGE_TO_SETTLE_TIMEOUT = 15

DEFAULT_ENDPOINT_NAME = "alpha-sunshine"

DEFAULT_RETRY_DELAY = 2
DEFAULT_RETRY_TRIES = 5

_LOGGER = setup_logging(__name__)
_TRACE_LOGGER = make_trace_logger()


class ExtensionDispatcher(ActDispatcher):
    """Dispatch act prompts to the Chrome Extension."""

    # Map workflow run IDs to act() statement IDs, for parsing return values.
    WORKFLOW_STATEMENTS: dict[str, str] = {}

    def __init__(
        self,
        backend_info: BackendInfo,
        nova_act_api_key: str | None,
        playwright_manager: PlaywrightInstanceManager,
        extension_path: str,
        tty: bool,
        verbose_errors: bool = False,
        retry: bool = True,
        boto_session: Session | None = None,
    ):
        self._backend_info = backend_info
        self._nova_act_api_key = nova_act_api_key
        self._playwright_manager = playwright_manager
        self._tty = tty
        self._verbose_errors = verbose_errors
        self._retry = retry
        self._boto_session = boto_session

        self._extension_version = get_extension_version(extension_path)

    def _poll_playwright(self, timeout_s: float) -> None:
        try:
            self._playwright_manager.main_page.evaluate("() => {}")
        # suppress trace during polling
        except PlaywrightError as e:
            if self._verbose_errors:
                _LOGGER.error(f"{type(e).__name__}", exc_info=True)
        time.sleep(timeout_s)

    def cancel_prompt(self, act: Act | None = None) -> None:
        """Dispatch a cancel message to the extension.

        Post a message with `type: autonomy-cancel-prompt` within the browser context.
        The extension listens for messages of this type to cancel existing program runs.

        """
        cancel_prompt_message = {"type": CANCEL_PROMPT_TYPE}
        encrypted_message = self._playwright_manager.encrypter.encrypt(cancel_prompt_message)
        try:
            self._playwright_manager.main_page.evaluate(POST_MESSAGE_EXPRESSION, encrypted_message)
        except PlaywrightError:
            if self._verbose_errors:
                _LOGGER.error("Encountered PlaywrightError", exc_info=True)

        if act is None:
            return

        end_time = time.time() + EXTENSION_TIMEOUT_S
        while time.time() < end_time:
            if act.is_complete:
                return
            else:
                self._poll_playwright(EXTENSION_POLL_SLEEP_S)

        raise ActDispatchError(
            message="Failed to cancel Act", metadata=act.metadata, extension_version=self._extension_version
        )

    def wait_for_page_to_settle(self, session_id: str, timeout: int | None = None) -> None:
        """
        Dispatch a page state query to extension and wait for confirmation of settled.
        """
        page_state = PageState(session_id)

        if timeout is None:
            timeout = MAX_WAIT_FOR_PAGE_TO_SETTLE_TIMEOUT

        self._playwright_manager.window_message_handler.bind_page(page_state)
        request_wait_for_page_state_message = {
            "type": WAIT_FOR_PAGE_TO_SETTLE_PROMPT_TYPE,
            "apiKey": self._nova_act_api_key,
            "uuid": str(uuid.uuid4()),
            "hostname": self._backend_info.api_uri,
            "sessionId": session_id,
            "useBedrock": True,
            "maxTimeout": timeout,
        }


        encrypted_message = self._playwright_manager.encrypter.encrypt(request_wait_for_page_state_message)

        try:
            self._playwright_manager.main_page.evaluate(POST_MESSAGE_EXPRESSION, encrypted_message)
        except PlaywrightError:
            if self._verbose_errors:
                _LOGGER.error("Encountered PlaywrightError", exc_info=True)

        end_time = time.time() + EXTENSION_TIMEOUT_S + timeout
        while time.time() < end_time:
            if page_state.is_settled:
                return
            else:
                self._poll_playwright(EXTENSION_POLL_SLEEP_S)

        _LOGGER.warning(f"Page not settled after {timeout}s")

    def go_to_url(self, url: str, session_id: str, timeout: int | None = None) -> None:
        """Navigates to the specified URL and waits for the page to settle."""

        self._playwright_manager.main_page.goto(url, wait_until="domcontentloaded")
        self._playwright_manager.main_page.wait_for_selector("#autonomy-listeners-registered", state="attached")
        self.wait_for_page_to_settle(session_id, timeout=timeout)

    def _dispatch_prompt_and_wait_for_ack(self, act: Act) -> None:
        """Dispatch an act prompt to the extension.

        Post a message with `type: autonomy-pending-prompt` within the browser context.
        The extension listens for messages of this type to initiate program runs.

        See also:
        * https://developer.mozilla.org/en-US/docs/Web/API/Window/postMessage

        """
        pending_action_message: Dict[str, Any] = {
            "type": DISPATCH_PROMPT_TYPE,
            "pendingPrompt": act.prompt,
            "apiKey": self._nova_act_api_key,
            "uuid": act.id,
            "endpointName": act.endpoint_name,
            "hostname": self._backend_info.api_uri,
            "sessionId": act.session_id,
            "useBedrock": True,
        }
        if self._boto_session:
            pending_action_message["awsCredentials"] = self._get_boto_session_credentials()
        if act.max_steps:
            pending_action_message["maxSteps"] = str(act.max_steps)
        if act.model_temperature is not None:
            pending_action_message["modelTemperature"] = str(act.model_temperature)
        if act.model_top_k is not None:
            pending_action_message["modelTopK"] = str(act.model_top_k)
        if act.model_seed is not None:
            pending_action_message["modelSeed"] = str(act.model_seed)

        encrypted_message = self._playwright_manager.encrypter.encrypt(pending_action_message)

        try:
            self._playwright_manager.main_page.evaluate(POST_MESSAGE_EXPRESSION, encrypted_message)
        except PlaywrightError:
            if self._verbose_errors:
                _LOGGER.error("Encountered PlaywrightError", exc_info=True)

        end_time = time.time() + EXTENSION_TIMEOUT_S
        while time.time() < end_time:
            if act.acknowledged:
                return
            else:
                self._poll_playwright(EXTENSION_POLL_SLEEP_S)

        raise ActDispatchError(
            message="Failed to receive Acknowledgment after dispatching a prompt to browser",
            metadata=act.metadata,
            extension_version=self._extension_version,
        )

    def dispatch_and_wait_for_prompt_completion(self, act: Act) -> ActResult | ActError:
        """Dispatch a pending act prompt and wait for reply from the extension.

        Calls `self._dispatch_prompt_and_wait_for_ack` to (1) add the pending prompt to
        `self._dispatched_prompts` and (2) post the message to the window. We then
        wait until the result appears in `self._completed_prompts`, which
        triggers when the extension posts a completion message to the console and
        `self.handle_autonomy_completion_message` adds it to `self._completed_prompts`.

        """
        self._playwright_manager.window_message_handler.bind(act)
        _LOGGER.debug(f"SDK version: {SDK_VERSION}")
        _LOGGER.debug(f"Extension version: {self._extension_version}")

        kb_cm: KeyboardEventWatcher | ContextManager[None] = (
            KeyboardEventWatcher(chr(24), "ctrl+x", "stop agent act() call without quitting the browser")
            if self._tty
            else nullcontext()
        )


        with kb_cm as watcher:
            # dispatch request to Extension
            retry_call(
                self._dispatch_prompt_and_wait_for_ack,
                fkwargs={"act": act},
                exceptions=ActDispatchError,
                delay=DEFAULT_RETRY_DELAY,
                tries=DEFAULT_RETRY_TRIES if self._retry else 1,
            )

            scroller = LoadScroller(frequency=5)

            end_time = time.time() + act.timeout
            num_steps_observed = 0
            while time.time() < end_time:

                self._poll_playwright(DEFAULT_POLL_SLEEP_S)
                if not is_quiet():
                    scroller.scroll()

                if len(act.steps) > num_steps_observed:
                    for step in act.steps[num_steps_observed:]:
                        model_response = step.model_output.awl_raw_program
                        newline = "\n"
                        formatted_response = (
                            f"\n{get_session_id_prefix()}{model_response.replace(newline, newline + '>> ')}"
                        )
                        _TRACE_LOGGER.info(formatted_response)
                    num_steps_observed = len(act.steps)

                if self._tty:
                    assert watcher is not None
                    triggered = watcher.is_triggered()
                    if triggered:
                        _TRACE_LOGGER.info(f"\n{get_session_id_prefix()}Terminating agent workflow")
                        self.cancel_prompt(act)

                if act.is_complete:
                    break

            else:
                act.did_timeout = True
                self.cancel_prompt(act)

            result = act.result
            output: ActResult | ActError

            if isinstance(result, ActCanceled):
                output = ActCanceledError(metadata=act.metadata)

            elif isinstance(result, ActFailed):
                output = parse_errors(act, self._backend_info, self._extension_version)

            elif isinstance(result, ActSucceeded):
                output = ActResult(
                    response=result.response,
                    metadata=act.metadata,
                )

            else:
                output = ActClientError(message="Unhandled act result", metadata=act.metadata)


            return output

    def _get_boto_session_credentials(self) -> Dict[str, str]:
        """Get IAM credentials from boto session to dispatch to the extension."""
        if not self._boto_session:
            return {}

        credentials = self._boto_session.get_credentials()
        if not credentials:
            raise IAMAuthError("No IAM credentials found in boto session!")

        credentials_dict = {
            "accessKeyId": credentials.access_key,
            "secretAccessKey": credentials.secret_key,
            "region": "us-east-1",  # Hardcoded to us-east-1 as Nova Act service only works in this region
        }
        if credentials.token is not None:
            credentials_dict["sessionToken"] = credentials.token

        return credentials_dict


class ExtensionActuator(BrowserActuatorBase, PlaywrightPageManagerBase):

    def __init__(self, dispatcher: ExtensionDispatcher):
        self._extension_dispatcher = dispatcher

    def agent_click(
        self, box: str, click_type: str | None = None, click_options: str | None = None
    ) -> JSONSerializable:
        raise NotImplementedError("agent_click is not implemented")

    def agent_scroll(self, direction: str, box: str, value: float | None = None) -> JSONSerializable:
        raise NotImplementedError("agent_scroll is not implemented")

    def agent_type(self, value: str, box: str, pressEnter: bool = False) -> JSONSerializable:
        raise NotImplementedError("agent_type is not implemented")

    def go_to_url(self, url: str) -> JSONSerializable:
        raise NotImplementedError("go_to_url is not implemented")

    def _return(self, value: str) -> JSONSerializable:
        raise NotImplementedError("_return is not implemented")

    def think(self, value: str) -> JSONSerializable:
        raise NotImplementedError("think is not implemented")

    def throw_agent_error(self, value: str) -> JSONSerializable:
        raise NotImplementedError("throw_agent_error is not implemented")

    def wait(self, seconds: float) -> JSONSerializable:
        raise NotImplementedError("wait is not implemented")

    def wait_for_page_to_settle(self) -> JSONSerializable:
        raise NotImplementedError("wait_for_page_to_settle is not implemented")

    def take_observation(self) -> BrowserObservation:
        raise NotImplementedError("take_observation is not implemented")

    def get_page(self, index: int = -1) -> Page:
        return self._extension_dispatcher._playwright_manager.get_page(index)

    @property
    def pages(self) -> list[Page]:
        return self._extension_dispatcher._playwright_manager.context.pages

    @property
    def started(self, **kwargs: Any) -> bool:
        return self._extension_dispatcher._playwright_manager.started

    def start(self, **kwargs: Any) -> None:
        if "session_logs_directory" in kwargs:
            self._extension_dispatcher._playwright_manager.start(
                session_logs_directory=kwargs.get("session_logs_directory")
            )
        if os.environ.get("PW_EXPERIMENTAL_SERVICE_WORKER_NETWORK_EVENTS"):
            StepServerTimeTracker(
                self._extension_dispatcher._playwright_manager.context,
                endpoint_pattern=self._extension_dispatcher._backend_info.api_uri,
            )

    def stop(self, **kwargs: Any) -> None:
        self._extension_dispatcher._playwright_manager.stop()
