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
"""Error handling decorators for browser CLI commands."""

import functools
import logging
import sys
from collections.abc import Callable
from typing import NamedTuple, TypeVar

import click

from nova_act.cli.browser.utils.log_capture import _build_log_path, _write_metadata_header
from nova_act.cli.core.exceptions import (
    BrowserProcessDead,
    SessionLimitReached,
    SessionLockTimeout,
)
from nova_act.cli.core.json_output import ErrorCode, is_json_mode, json_error
from nova_act.cli.core.output import (
    exit_with_error,
    get_current_log_path,
    is_verbose_mode,
    set_current_log_dir,
    set_current_log_path,
    set_verbose_mode,
)
from nova_act.types.act_errors import (
    ActExceededMaxStepsError,
    ActGuardrailsError,
    ActRateLimitExceededError,
    ActTimeoutError,
)
from nova_act.types.errors import AuthError, IAMAuthError

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., object])  # type: ignore[explicit-any]


def _get_failure_details(e: Exception) -> dict[str, str] | None:
    """Extract failure screenshot details from an exception, if attached."""
    screenshot = getattr(e, "_failure_screenshot", None)
    return {"failure_screenshot": screenshot} if screenshot else None


def _is_chrome_not_found(e: Exception) -> bool:
    """Check if an exception indicates Chrome was not found."""
    msg = str(e).lower()
    return "chrome" in msg and ("not found" in msg or "no such file" in msg or "executable" in msg)


def _handle_chrome_not_found(e: Exception, details: dict[str, str] | None) -> bool:
    """Handle Chrome-not-found errors. Returns True if the error was handled."""
    if not _is_chrome_not_found(e):
        return False
    exit_with_error(
        "Chrome not found",
        str(e),
        suggestions=[
            "Run 'act browser doctor' to diagnose browser issues",
            "Specify a custom path: --executable-path /path/to/chrome",
        ],
        error_code=ErrorCode.CHROME_NOT_FOUND,
        details=details,
    )
    return True  # exit_with_error calls sys.exit, but needed for testability


def _is_browser_validation_error(e: Exception) -> bool:
    """Check if an exception is a browser validation error with a specific message."""
    msg = str(e).lower()
    return any(
        indicator in msg for indicator in ["not chromium", "not a directory", "invalid profile", "missing preferences"]
    )


def _handle_browser_validation_error(e: Exception, details: dict[str, str] | None) -> bool:
    """Handle browser validation errors (non-chromium, bad profile, etc.). Returns True if handled."""
    if not isinstance(e, RuntimeError) or not _is_browser_validation_error(e):
        return False
    exit_with_error(
        "Browser validation failed",
        str(e),
        suggestions=[
            "Verify the browser is Chromium-based (Chrome, Chromium, or Edge)",
            "Ensure the profile path is a valid directory with a Preferences file",
        ],
        error_code=ErrorCode.VALIDATION_ERROR,
        details=details,
    )
    return True  # exit_with_error calls sys.exit, but needed for testability


def _handle_runtime_error(e: Exception, details: dict[str, str] | None) -> bool:
    """Handle RuntimeError with generic browser error messaging. Returns True if handled."""
    if not isinstance(e, RuntimeError) or isinstance(e, click.exceptions.Exit):
        return False
    exit_with_error(
        str(e),
        "A runtime error occurred during command execution.",
        suggestions=["Check browser installation", "Verify system resources are available"],
        error_code=ErrorCode.BROWSER_ERROR,
        details=details,
    )
    return True  # exit_with_error calls sys.exit, but needed for testability


class _SdkErrorMapping(NamedTuple):
    """Maps an SDK error type to its user-facing error presentation."""

    error_type: type[Exception]
    title: str
    default_message: str
    suggestions: list[str]
    error_code: ErrorCode
    retryable: bool


_SDK_ERROR_MAP: list[_SdkErrorMapping] = [
    _SdkErrorMapping(
        IAMAuthError,
        "AWS authentication failed",
        "",
        [
            "Verify credentials: aws sts get-caller-identity --profile <profile>",
            "Refresh credentials: ada credentials update --profile <profile> ...",
            "Check region: --region us-east-1",
        ],
        ErrorCode.AUTH_ERROR,
        False,
    ),
    _SdkErrorMapping(
        AuthError,
        "Authentication failed",
        "",
        [
            "Verify your API key: --nova-arg nova_act_api_key=<key>",
            "Or switch to AWS auth: --auth-mode aws --aws-profile <profile>",
        ],
        ErrorCode.AUTH_ERROR,
        False,
    ),
    _SdkErrorMapping(
        ActTimeoutError,
        "Action timed out",
        "The act() call exceeded its timeout.",
        [
            "Increase --timeout or simplify the prompt",
            "Break complex actions into smaller steps",
        ],
        ErrorCode.ACT_TIMEOUT_ERROR,
        True,
    ),
    _SdkErrorMapping(
        ActExceededMaxStepsError,
        "Max steps exceeded",
        "The action exceeded the maximum number of steps.",
        [
            "Increase max_steps: --nova-arg max_steps=<N>",
            "Simplify the prompt to require fewer steps",
        ],
        ErrorCode.ACT_MAX_STEPS_ERROR,
        True,
    ),
    _SdkErrorMapping(
        ActGuardrailsError,
        "Guardrails blocked action",
        "The action was blocked by safety guardrails.",
        [
            "Rephrase the prompt to avoid restricted content",
            "Review guardrail policies for your account",
        ],
        ErrorCode.ACT_GUARDRAILS_ERROR,
        False,
    ),
    _SdkErrorMapping(
        ActRateLimitExceededError,
        "Rate limit exceeded",
        "API rate limit exceeded.",
        [
            "Wait and retry after a short delay",
            "Reduce request frequency",
        ],
        ErrorCode.ACT_RATE_LIMIT_ERROR,
        True,
    ),
]


def _handle_sdk_error(e: Exception, details: dict[str, str] | None) -> bool:
    """Handle SDK-specific errors. Returns True if the error was handled."""
    for mapping in _SDK_ERROR_MAP:
        if isinstance(e, mapping.error_type):
            exit_with_error(
                mapping.title,
                str(e) or mapping.default_message,
                suggestions=mapping.suggestions,
                error_code=mapping.error_code,
                retryable=mapping.retryable,
                details=details,
            )
            return True  # exit_with_error calls sys.exit, but needed for testability
    return False


def _handle_keyboard_interrupt(session_id: str) -> None:
    """Handle KeyboardInterrupt with JSON or text output, then exit."""
    log_path = get_current_log_path()
    if is_json_mode():
        json_error(
            ErrorCode.INTERRUPTED, f"Operation interrupted. Session '{session_id}' preserved.", log_path=log_path
        )
        sys.exit(130)
    click.echo(
        f"\nInterrupted. Session '{session_id}' preserved "
        f"— use 'act browser session close {session_id}' to clean up."
    )
    if log_path:
        from pathlib import Path

        click.echo(f"log_dir: {str(Path(log_path).parent)}")
    sys.exit(130)


def handle_common_errors(func: F) -> F:  # type: ignore[explicit-any]
    """Decorator to handle common browser command errors."""

    @functools.wraps(func)
    def wrapper(*args: object, **kwargs: object) -> object:
        if kwargs.get("verbose"):
            set_verbose_mode(True)
        # Set up log path early so exit_with_error always has a valid log path,
        # even for errors that fire before command_session() enters capture_command_log().
        # If command_session() runs later, it overwrites these with the real values.
        if not get_current_log_path():
            session_id = str(kwargs.get("session_id", "default"))
            command_name = func.__name__.replace("_", "-")
            log_path, cmd_dir = _build_log_path(session_id, command_name)
            set_current_log_path(str(log_path))
            set_current_log_dir(str(cmd_dir))
            # Create a minimal log.txt so it exists even if the command fails before
            # entering capture_command_log(). Commands that use command_session() will
            # overwrite this file with the full version including SDK output.
            # Best-effort: capture_command_log will retry later if this fails.
            try:
                with open(log_path, "w") as f:
                    _write_metadata_header(f, command_name, session_id, None)
            except OSError:
                pass
        try:
            return func(*args, **kwargs)
        except click.exceptions.Exit:
            raise
        except KeyboardInterrupt:
            _handle_keyboard_interrupt(str(kwargs.get("session_id", "default")))
        except SessionLockTimeout as e:
            exit_with_error(
                "Session is busy",
                str(e),
                suggestions=["Wait for the current operation to complete", "Use a different session with --session-id"],
                error_code=ErrorCode.SESSION_BUSY,
                retryable=True,
            )
        except SessionLimitReached as e:
            exit_with_error(
                "Session limit reached",
                str(e),
                suggestions=[
                    "Close unused sessions: act browser session close-all",
                    "Prune stale sessions: act browser session prune",
                    "Increase limit: --max-sessions <N>",
                ],
                error_code=ErrorCode.SESSION_LIMIT_REACHED,
            )
        except BrowserProcessDead as e:
            exit_with_error(
                "Browser process died",
                str(e),
                suggestions=[
                    "Close the session: act browser session close --force",
                    "Create a new session: act browser session create <url>",
                ],
                error_code=ErrorCode.BROWSER_ERROR,
            )
        except ConnectionError as e:
            exit_with_error(
                "Connection failed",
                str(e),
                suggestions=[
                    "Check network connectivity",
                    "Verify the browser process is running",
                    "Retry the command",
                ],
                error_code=ErrorCode.BROWSER_ERROR,
                retryable=True,
            )
        except TimeoutError as e:
            exit_with_error(
                "Operation timed out",
                str(e),
                suggestions=["Retry the command", "Increase timeout if available", "Check system resources"],
                error_code=ErrorCode.TIMEOUT_ERROR,
                retryable=True,
            )
        except PermissionError as e:
            exit_with_error(
                "Permission denied",
                str(e),
                suggestions=["Check file and directory permissions", "Run with appropriate user privileges"],
                error_code=ErrorCode.FILE_ERROR,
            )
        except (
            Exception
        ) as e:  # noqa: BLE001 — top-level CLI error boundary; catches anything not handled by specific handlers above
            details = _get_failure_details(e)
            if _handle_sdk_error(e, details):
                return None
            if _handle_chrome_not_found(e, details):
                return None
            if _handle_browser_validation_error(e, details):
                return None
            if _handle_runtime_error(e, details):
                return None
            if is_verbose_mode():
                logger.error("Unexpected error in %s", func.__name__, exc_info=True)
            else:
                logger.warning("Unexpected error in %s: %s", func.__name__, e)
            exit_with_error(
                f"{func.__name__.replace('_', ' ').title()} failed",
                str(e),
                suggestions=["Check that the browser session is active", "Try again or use a different session"],
                error_code=ErrorCode.UNEXPECTED_ERROR,
                details=details,
            )
        return None

    return wrapper  # type: ignore[return-value]
