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

from deprecated import deprecated
from typing_extensions import Callable, Type

from nova_act.types.act_metadata import ActMetadata
from nova_act.types.errors import NovaActError



MAX_CHARS = 500


def set_default_message(default_message: str) -> Callable[[Type[ActError]], Type[ActError]]:
    """Set the default message of an ActError subclass."""

    def decorator(cls: Type[ActError]) -> Type[ActError]:
        cls._DEFAULT_MESSAGE = default_message
        return cls

    return decorator


class ActError(NovaActError):
    """Superclass for all errors encountered during `act` execution.

    ActMetadata objects may be injected post-init to provide context
    on the current run.
    """

    _DEFAULT_MESSAGE = "An error occurred during act()"

    def __init__(self, message: str | None = None, metadata: ActMetadata | None = None):
        _message = message or type(self)._DEFAULT_MESSAGE
        super().__init__(_message)
        self.message = _message
        self.metadata = metadata

    def __str__(self) -> str:
        try:
            # Get all attributes
            fields = vars(self)

            # Create lines
            field_strings = []
            metadata_str = ""
            for field_name, value in fields.items():
                if value is not None:  # Only include non-None value
                    if field_name == "metadata":
                        line_break = "\n"
                        metadata_str = f"    {field_name} = {str(value).replace(line_break, line_break + '    ')}"
                    else:
                        field_strings.append(f"    {field_name} = {str(value)[:MAX_CHARS]}")

            if metadata_str:
                field_strings.append(metadata_str)
            fields_str = "\n".join(field_strings)
            return (
                f"\n\n{self.__class__.__name__}(\n"
                f"{fields_str}\n"
                f")"
                "\n\nPlease consider providing feedback: "
                "https://amazonexteu.qualtrics.com/jfe/form/SV_bd8dHa7Em6kNkMe"
            )
        except Exception as e:
            return f"Error in __str__: {e}"


@set_default_message("Timed out; try increasing the 'timeout' kwarg on the 'act' call")
class ActTimeoutError(ActError):
    """Indicates an act call timed out."""


class ActAgentError(ActError):
    """Indicates the provided prompt cannot be completed in the given configuration."""


@set_default_message("The model output could not be processed. Please try a different request.")
class ActInvalidModelGenerationError(ActAgentError):
    """Indicates the Act model failed or produced invalid output."""

    def __init__(
        self,
        message: str | None = None,
        metadata: ActMetadata | None = None,
        raw_response: str | None = None,
    ):
        super().__init__(message=message, metadata=metadata)
        self.raw_response = raw_response




@set_default_message("The requested action was not possible")
class ActAgentFailed(ActAgentError):
    """Indicates the model raised an error because it could not complete the request."""


@set_default_message("Allowed Steps Exceeded")
class ActExceededMaxStepsError(ActAgentError):
    """Indicates an Act session exceeded the maximum allowed steps."""


class ActExecutionError(ActError):
    """Indicates an error encountered during client execution."""


@set_default_message("Act Canceled.")
class ActCanceledError(ActExecutionError):
    """Indicates the client received a cancel signal and stopped."""


@set_default_message("Human input required to proceed. Implement and provide human_input_callbacks.")
class NoHumanInputToolAvailable(ActInvalidModelGenerationError):
    """Indicates the model requested human input but no callbacks were provided."""


@set_default_message("Act Canceled during Human Approval.")
class ApproveCanceledError(ActCanceledError):
    """Indicates the client received a cancel response during human approval and stopped."""


@set_default_message("Act Canceled during Human UI Takeover.")
class UiTakeoverCanceledError(ActCanceledError):
    """Indicates the client received a cancel signal during human UI takeover and stopped."""


@set_default_message("Encountered error actuating model actions.")
class ActActuationError(ActExecutionError):
    """Indicates the client failed to actuate a given command from the agent."""


@set_default_message("Failed to invoke a tool.")
class ActToolError(ActExecutionError):
    """Indicates a failure running a tool."""


@set_default_message("Failed to invoke MCP tool.")
class ActMCPError(ActToolError):
    """Indicates a failure running an MCP-provided tool."""


@set_default_message("Blocked by agent state guardrail")
class ActStateGuardrailError(ActExecutionError):
    """Indicates a client-provided agent state guardrail triggered."""


class ActAPIError(ActError):
    """Errors caused by a breach of contract between client/server."""

    def __init__(
        self,
        request_id: str | None = None,
        status_code: int | None = None,
        message: str | None = None,
        raw_response: str | None = None,
        metadata: ActMetadata | None = None,
    ):
        super().__init__(message=message, metadata=metadata)
        self.request_id = request_id
        self.status_code = status_code
        self.raw_response = raw_response


@set_default_message("Client error calling NovaAct Service.")
class ActClientError(ActAPIError):
    """Errors caused by bad requests to NovaAct Service.

    Indicates that users may retry with a different request.
    """


@set_default_message("Bad request")
class ActBadRequestError(ActClientError):
    """Indicates a bad request to /step endpoint."""


@set_default_message(
    "I'm sorry, but I can't engage in unsafe or inappropriate actions. Please try a different request."
)
class ActGuardrailsError(ActClientError):
    """Indicates an Act request was blocked by the agent guardrails system."""


@set_default_message(
    "We have quota limits to ensure sufficient capacity for all users. If you need dedicated "
    "quota for a more ambitious project, please request a limit increase by filling out "
    "https://amazonexteu.qualtrics.com/jfe/form/SV_3V3pUMJFeMWpq1o. "
    "We're excited to see what you build!"
)
class ActRateLimitExceededError(ActClientError):
    """Indicates a request for an Act session was throttled."""


@set_default_message("Too many requests in a short time period. " + ActRateLimitExceededError._DEFAULT_MESSAGE)
class ActRequestThrottledError(ActRateLimitExceededError):
    """Indicates a request was throttled due to too many requests in a short time."""


@set_default_message("Daily API limit exceeded. " + ActRateLimitExceededError._DEFAULT_MESSAGE)
class ActDailyQuotaExceededError(ActRateLimitExceededError):
    """Indicates a request was rejected as the user's daily quota has been exceeded."""


@set_default_message("Error calling NovaAct Service.")
class ActServerError(ActAPIError):
    """Error caused by bad responses from NovaAct Service.

    Indicates an issue with the service that should be reported to customer support.
    """


@set_default_message("Bad Response")
class ActBadResponseError(ActServerError):
    """Indicates a bad response from the /step endpoint."""


@set_default_message("NovaAct Service Unavailable")
class ActServiceUnavailableError(ActServerError):
    """Indicates the /step endpoint is currently unavailable."""


@set_default_message("Internal Server Error")
class ActInternalServerError(ActServerError):
    """Indicates an internal server error occurred while processing an Act request."""


# Deprecated


@deprecated(version="2.1.0", reason="Rolled into ActClientError.")
class ActPromptError(ActError):
    """Represents an error specific to the given prompt."""


@deprecated(version="2.1.0", reason="Renamed to ActInvalidModelGenerationError.")
class ActModelError(ActPromptError):
    """The model output could not be processed."""


@deprecated(version="2.1.0", reason="This error will no longer be raised as the Chrome extension has been deprecated.")
class ActDispatchError(ActClientError):
    """Failed to dispatch Act."""


@deprecated(version="2.1.0", reason="No longer raised; roughly correlates with new ActAPIError.")
class ActProtocolError(ActAPIError):
    """Failed to parse response from Chrome extension."""


@deprecated(version="2.1.0", reason="Rolled into ActBadRequestError.")
class ActInvalidInputError(ActClientError):
    """Invalid input to model."""
