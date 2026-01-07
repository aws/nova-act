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
from abc import ABC


class NovaActError(Exception, ABC):
    """Superclass for all NovaAct client exceptions."""


"""
Wrapper classes for unhandled exceptions
"""


class StartFailed(NovaActError):
    """Exception raised when the client fails during start() for an otherwise unhandled reason."""


class StopFailed(NovaActError):
    """Exception raised when the client fails during stop() for an otherwise unhandled reason."""


class PauseFailed(NovaActError):
    """Exception raised when the client fails during stop() for an otherwise unhandled reason."""


class ResumeFailed(NovaActError):
    """Exception raised when the client fails during stop() for an otherwise unhandled reason."""


class CancelFailed(NovaActError):
    """Exception raised when the client fails during stop() for an otherwise unhandled reason."""


"""
Known Usage Errors
"""


class AuthError(NovaActError):
    """Indicates there's error with user auth"""

    def __init__(self, message: str):
        super().__init__(message)




class IAMAuthError(NovaActError):
    """Indicates there's an error with IAM credentials"""

    def __init__(self, message: str | None = "IAM authentication failed."):
        super().__init__(message)


class ValidationFailed(NovaActError, ABC):
    """Indicates assumptions violated about how the SDK can be used"""


class ClientNotStarted(ValidationFailed):
    pass


class InvalidPlaywrightState(NovaActError):
    pass


class InvalidPageState(NovaActError):
    pass


class UnsupportedOperatingSystem(ValidationFailed):
    pass


class InvalidInputLength(ValidationFailed):
    pass


class InvalidScreenResolution(ValidationFailed):
    pass


class InvalidPath(ValidationFailed):
    pass


class InvalidURL(ValidationFailed):
    pass


class InvalidCertificate(ValidationFailed):
    pass


class InvalidTimeout(ValidationFailed):
    pass


class InvalidMaxSteps(ValidationFailed):
    def __init__(self, num_steps_allowed: int):
        super().__init__(f"Please choose a number less than {num_steps_allowed}")


class InvalidChromeChannel(ValidationFailed):
    pass


class PageNotFoundError(ValidationFailed):
    pass


class InterpreterError(NovaActError):
    """Indicates an error encountered while interpreting model output."""


class InvalidTrajectoryReplay(NovaActError):
    """Indicates a Trajectory is being replayed on an invalid environment."""
