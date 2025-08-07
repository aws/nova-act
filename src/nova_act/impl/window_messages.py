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
from nova_act.impl.message_encrypter import ENCRYPTED_MESSAGE_TYPE, MessageEncrypter
from nova_act.types.state.act import Act
from nova_act.types.state.page import PageState
from nova_act.types.state.step import Step
from nova_act.util.logging import setup_logging
from nova_act.util.step_server_time_tracker import StepServerTimeTracker

CANCEL_PROMPT_TYPE = "autonomy-cancel-prompt"
WAIT_FOR_PAGE_TO_SETTLE_PROMPT_TYPE = "autonomy-pending-wait-for-page-to-settle"
REQUEST_ACCEPTED_PROMPT_TYPE = "autonomy-request-accepted"
COMPLETION_PROMPT_TYPE = "autonomy-prompt-completion"
DISPATCH_PROMPT_TYPE = "autonomy-pending-prompt"
TAB_UPDATE_PROMPT_TYPE = "autonomy-update-active-tab"
STEP_OBSERVATION_PROMPT_TYPE = "autonomy-step-observation"

POST_MESSAGE_EXPRESSION = """
(message) => {
    window.postMessage(message);
}
"""

HANDLE_ENCRYPTED_MESSAGE_FUNCTION_NAME = "handleEncryptedMessage"

ADD_COMPLETION_LISTENER_EXPRESSION = f"""
() => {{
    window.addEventListener("{ENCRYPTED_MESSAGE_TYPE}", (event) => {{
        const encryptedMessage = event.detail.encryptedMessage;
        {HANDLE_ENCRYPTED_MESSAGE_FUNCTION_NAME}(encryptedMessage);
    }});
}}
"""

_LOGGER = setup_logging(__name__)


class WindowMessageHandler:
    """Handle window messages from the extension."""

    def __init__(self, encrypter: MessageEncrypter) -> None:
        self._act: Act | None = None
        self._page_state: PageState | None = None
        self._encrypter: MessageEncrypter = encrypter

    def bind(self, act: Act) -> None:
        """Bind an active Act object for accumulating observations"""
        if act.is_complete:
            raise ValueError("Cannot bind a completed act for more observations")
        self._act = act
        self._page_state = None

    def bind_page(self, page_state: PageState) -> None:
        if page_state.is_settled:
            raise ValueError("Cannot bind a settled page for more observations")
        self._act = None
        self._page_state = page_state

    def handle_message(self, encrypted_message: dict | str) -> None:
        """Register observations in bound Act, if any"""
        try:
            _LOGGER.debug("Got message %s", encrypted_message)
            if isinstance(encrypted_message, str) and encrypted_message == "ping":
                return
            if not isinstance(encrypted_message, dict):
                raise ValueError("Message must be a dict")

            message = self._encrypter.decrypt(encrypted_message)
            if message is None:
                return
            _LOGGER.debug("Decrypted %s", message)
            message_type = message.get("type")

            if self._page_state is not None:
                if message_type == COMPLETION_PROMPT_TYPE:
                    self._page_state.is_settled = True

            if self._act is not None:
                if message_type == COMPLETION_PROMPT_TYPE:

                    response = message.get("response")
                    if response is None:
                        raise ValueError("Completion message missing response")

                    completion_type = response.get("type")
                    if completion_type == "success":
                        self._act.complete(response.get("result"))
                    elif completion_type == "canceled":
                        self._act.cancel()
                    elif completion_type == "error":
                        self._act.fail(response)

                if message_type == REQUEST_ACCEPTED_PROMPT_TYPE:
                    self._act.acknowledged = True

                if message_type == STEP_OBSERVATION_PROMPT_TYPE:
                    maybe_server_time_tracker = StepServerTimeTracker.get_instance()
                    if maybe_server_time_tracker is not None:
                        message["server_time_s"] = maybe_server_time_tracker.get_step_duration_s(act_id=self._act.id)
                    self._act.add_step(Step.from_message(message))

        except Exception as ex:
            _LOGGER.error("Error handling message in dispatcher: %s", ex, exc_info=True)
            raise
