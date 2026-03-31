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
"""JSON output mode for Nova Act CLI agent integration."""

import json
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum

import click

from nova_act.cli.core.cli_stdout import get_cli_stdout

_json_mode: ContextVar[bool] = ContextVar("_json_mode", default=False)


class ErrorCode(str, Enum):
    """Error codes for structured JSON error responses."""

    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    SESSION_BUSY = "SESSION_BUSY"
    SESSION_EXISTS = "SESSION_EXISTS"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    BROWSER_ERROR = "BROWSER_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    NAVIGATION_ERROR = "NAVIGATION_ERROR"
    FILE_ERROR = "FILE_ERROR"
    INTERRUPTED = "INTERRUPTED"
    SESSION_LIMIT_REACHED = "SESSION_LIMIT_REACHED"
    AUTH_ERROR = "AUTH_ERROR"
    ACT_TIMEOUT_ERROR = "ACT_TIMEOUT_ERROR"
    ACT_MAX_STEPS_ERROR = "ACT_MAX_STEPS_ERROR"
    ACT_GUARDRAILS_ERROR = "ACT_GUARDRAILS_ERROR"
    ACT_RATE_LIMIT_ERROR = "ACT_RATE_LIMIT_ERROR"
    CHROME_NOT_FOUND = "CHROME_NOT_FOUND"
    ASSERTION_FAILED = "ASSERTION_FAILED"
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"


@dataclass(frozen=True)
class JsonResponse:
    """Structured JSON response payload for CLI agent integration.

    Attributes:
        status: Response status — "success" or "error".
        data: Response data payload.
        code: Error code (only for error responses).
        message: Error message (only for error responses).
        retryable: Whether the error is retryable (only for error responses).
        log: Path to command log file.
    """

    status: str
    data: dict[str, object] = field(default_factory=dict)
    code: str | None = None
    message: str | None = None
    retryable: bool = False
    log: str | None = None
    log_dir: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialize to dict, omitting None fields."""
        result: dict[str, object] = {"status": self.status, "data": self.data}
        if self.code is not None:
            result["code"] = self.code
        if self.message is not None:
            result["message"] = self.message
        if self.code is not None:
            result["retryable"] = self.retryable
        if self.log is not None:
            result["log"] = self.log
        if self.log_dir is not None:
            result["log_dir"] = self.log_dir
        return result


def is_json_mode() -> bool:
    """Check if JSON output mode is active."""
    return _json_mode.get()


def set_json_mode(enabled: bool) -> None:
    """Set JSON output mode."""
    _json_mode.set(enabled)


def _emit(response: JsonResponse) -> None:
    """Serialize and print a JsonResponse."""
    click.echo(json.dumps(response.to_dict(), default=str), file=get_cli_stdout())


def json_success(
    data: Mapping[str, object] | None = None, log_path: str | None = None, log_dir: str | None = None
) -> None:
    """Print structured JSON success response."""
    _emit(JsonResponse(status="success", data=dict(data) if data else {}, log=log_path, log_dir=log_dir))


def json_error(
    code: ErrorCode,
    message: str,
    retryable: bool = False,
    log_path: str | None = None,
    log_dir: str | None = None,
    details: Mapping[str, object] | None = None,
) -> None:
    """Print structured JSON error response."""
    _emit(
        JsonResponse(
            status="error",
            code=code.value,
            message=message,
            retryable=retryable,
            data=dict(details) if details else {},
            log=log_path,
            log_dir=log_dir,
        )
    )
