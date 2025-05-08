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
import time
import uuid
from contextlib import nullcontext
from dataclasses import replace
from typing import ContextManager, cast

from playwright.sync_api import Error as PlaywrightError
from retry.api import retry_call

from nova_act.__version__ import VERSION as SDK_VERSION
from nova_act.impl.backend import BackendInfo
from nova_act.impl.keyboard_event_watcher import KeyboardEventWatcher
from nova_act.impl.playwright import PlaywrightInstanceManager
from nova_act.impl.protocol import parse_errors
from nova_act.impl.run_info_compiler import RunInfoCompiler
from nova_act.impl.window_messages import (
    CANCEL_PROMPT_TYPE,
    DISPATCH_PROMPT_TYPE,
    POST_MESSAGE_EXPRESSION,
    WAIT_FOR_PAGE_TO_SETTLE_PROMPT_TYPE,
)
from nova_act.types.act_errors import ActCanceledError, ActClientError, ActDispatchError, ActError
from nova_act.types.act_result import ActResult
from nova_act.types.state.act import Act, ActCanceled, ActFailed, ActSucceeded
from nova_act.types.state.page import PageState
from nova_act.util.logging import LoadScroller, get_session_id_prefix, is_quiet, make_trace_logger, setup_logging

# Check every 0.5 seconds, for a total of 30 seconds.
DEFAULT_POLL_SLEEP_S = 0.5
DEFAULT_TIMEOUT_S = 30.0

# Give Extension 2s to accept the request; it should be instant
EXTENSION_POLL_SLEEP_S = 0.1
EXTENSION_TIMEOUT_S = 2.0
MAX_WAIT_FOR_PAGE_TO_SETTLE_TIMEOUT = 15

DEFAULT_ENDPOINT_NAME = "alpha-sunshine"

DEFAULT_RETRY_DELAY = 2
DEFAULT_RETRY_TRIES = 5

_LOGGER = setup_logging(__name__)
_TRACE_LOGGER = make_trace_logger()




class ExtensionDispatcher:
    """Dispatch act prompts to the Chrome Extension."""

    # Map workflow run IDs to act() statement IDs, for parsing return values.
    WORKFLOW_STATEMENTS: dict[str, str] = {}

    def __init__(
        self,
        backend_info: BackendInfo,
        nova_act_api_key: str,
        playwright_manager: PlaywrightInstanceManager,
        session_logs_directory: str | None,
        extension_version: str,
        tty: bool,
        session_id: str,
        verbose_errors: bool = False,
        retry: bool = True,
    ):
        self._backend_info = backend_info
        self._nova_act_api_key = nova_act_api_key
        self._playwright_manager = playwright_manager
        self._extension_version = extension_version
        self._tty = tty
        self._session_id = session_id
        self._verbose_errors = verbose_errors
        self._retry = retry

        self._run_info_compiler = RunInfoCompiler(session_logs_directory) if session_logs_directory else None

    def _poll_playwright(self, timeout_s: float):
        try:
            self._playwright_manager.main_page.evaluate("() => {}")
        # suppress trace during polling
        except PlaywrightError as e:
            if self._verbose_errors:
                _LOGGER.error(f"{type(e).__name__}", exc_info=True)
        time.sleep(timeout_s)

    @property
    def session_id(self) -> str:
        return self._session_id

    def cancel_prompt(self, act: Act | None = None):
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
            message="Failed to cancel Act",
            metadata=act.metadata,
        )

    def wait_for_page_to_settle(self, go_to_url_timeout: int | None = None) -> None:
        """
        Dispatch a page state query to extension and wait for confirmation of settled.
        """
        page_state = PageState(self._session_id)

        if go_to_url_timeout is None:
            go_to_url_timeout = MAX_WAIT_FOR_PAGE_TO_SETTLE_TIMEOUT

        self._playwright_manager.window_message_handler.bind_page(page_state)
        request_wait_for_page_state_message = {
            "type": WAIT_FOR_PAGE_TO_SETTLE_PROMPT_TYPE,
            "apiKey": self._nova_act_api_key,
            "uuid": str(uuid.uuid4()),
            "hostname": self._backend_info.api_uri,
            "sessionId": self._session_id,
            "useBedrock": True,
            "maxTimeout": go_to_url_timeout,
        }


        encrypted_message = self._playwright_manager.encrypter.encrypt(request_wait_for_page_state_message)

        try:
            self._playwright_manager.main_page.evaluate(POST_MESSAGE_EXPRESSION, encrypted_message)
        except PlaywrightError:
            if self._verbose_errors:
                _LOGGER.error("Encountered PlaywrightError", exc_info=True)

        end_time = time.time() + EXTENSION_TIMEOUT_S + go_to_url_timeout
        while time.time() < end_time:
            if page_state.is_settled:
                return
            else:
                self._poll_playwright(EXTENSION_POLL_SLEEP_S)

        _LOGGER.warning(f"Page not settled after {go_to_url_timeout}s")

    def _dispatch_prompt_and_wait_for_ack(self, act: Act):
        """Dispatch an act prompt to the extension.

        Post a message with `type: autonomy-pending-prompt` within the browser context.
        The extension listens for messages of this type to initiate program runs.

        See also:
        * https://developer.mozilla.org/en-US/docs/Web/API/Window/postMessage

        """
        pending_action_message = {
            "type": DISPATCH_PROMPT_TYPE,
            "pendingPrompt": act.prompt,
            "apiKey": self._nova_act_api_key,
            "uuid": act.id,
            "endpointName": act.endpoint_name,
            "hostname": self._backend_info.api_uri,
            "sessionId": self._session_id,
            "useBedrock": True,
        }
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

            scroller = LoadScroller(condition_check=lambda: len(act.steps) < 1)

            end_time = time.time() + act.timeout

            scroller = LoadScroller()

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

            if self._run_info_compiler:
                file_path = self._run_info_compiler.compile(act)
                _TRACE_LOGGER.info(f"\n{get_session_id_prefix()}** View your act run here: {file_path}\n")

            result = act.result
            output: ActResult | ActError

            if isinstance(result, ActCanceled):
                output = ActCanceledError(metadata=act.metadata)

            elif isinstance(result, ActFailed):
                output = parse_errors(act, self._backend_info)

            elif isinstance(result, ActSucceeded):
                output = ActResult(
                    response=result.response,
                    metadata=act.metadata,
                )

            else:
                output = ActClientError(message="Unhandled act result", metadata=act.metadata)


            return output
