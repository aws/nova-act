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
"""
Custom exception classes for Nova Act CLI.
"""


class NovaActCLIError(Exception):
    """Base exception for all Nova Act CLI errors."""

    pass


class ValidationError(NovaActCLIError):
    """Raised when input validation fails."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class DeploymentError(NovaActCLIError):
    """Raised when deployment operations fail."""

    pass


class ConfigurationError(NovaActCLIError):
    """Raised when configuration is invalid or missing."""

    pass


class WorkflowError(NovaActCLIError):
    """Raised when workflow operations fail."""

    pass


class WorkflowNameArnMismatchError(WorkflowError):
    """Raised when workflow name doesn't match the resource name in the ARN."""

    pass


class ExecutionError(NovaActCLIError):
    """Raised when runtime execution operations fail."""

    pass


class ImageBuildError(NovaActCLIError):
    """Raised when ECR image build operations fail."""

    pass


class CodeBuildError(NovaActCLIError):
    """Raised when CodeBuild operations fail."""

    pass


class SessionError(NovaActCLIError):
    """Base exception for session-related errors."""

    pass


class SessionLockTimeout(SessionError):
    """Raised when session lock cannot be acquired within timeout."""

    pass


class SessionNotFoundError(SessionError, KeyError):
    """Raised when a session ID is not found."""

    pass


class SessionLimitReached(SessionError):
    """Raised when the maximum number of active sessions is reached."""

    pass


class BrowserProcessDead(SessionError):
    """Raised when the browser process for a session is no longer running."""

    pass
