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
"""Output formatting utilities for Nova Act CLI."""

__all__ = [
    "EXIT_CODE_ERROR",
    "echo_success",
    "exit_with_error",
    "format_error",
    "format_info",
    "format_success",
    "get_cli_stdout",
    "get_current_log_path",
    "is_quiet_mode",
    "is_verbose_mode",
    "set_current_log_dir",
    "set_current_log_path",
    "set_original_stdout",
    "set_quiet_mode",
    "set_verbose_mode",
]

from collections.abc import Mapping
from contextvars import ContextVar
from typing import NoReturn, TextIO

import click

from nova_act.cli.core.cli_stdout import get_cli_stdout, set_original_stdout
from nova_act.cli.core.json_output import ErrorCode, is_json_mode, json_error, json_success
from nova_act.cli.core.styling import secondary, value
from nova_act.cli.core.theme import get_active_theme

# Constants
EXIT_CODE_ERROR = 1

# Verbose mode context var
_verbose_mode: ContextVar[bool] = ContextVar("_verbose_mode", default=False)

# Quiet mode context var
_quiet_mode: ContextVar[bool] = ContextVar("_quiet_mode", default=False)

# Log path context var — set by capture_command_log, read by output functions
_current_log_path: ContextVar[str | None] = ContextVar("_current_log_path", default=None)

# Log dir context var — set by capture_command_log, read by output functions
_current_log_dir: ContextVar[str | None] = ContextVar("_current_log_dir", default=None)


def is_verbose_mode() -> bool:
    """Check if verbose output mode is active."""
    return _verbose_mode.get()


def set_verbose_mode(enabled: bool) -> None:
    """Set verbose output mode."""
    _verbose_mode.set(enabled)


def is_quiet_mode() -> bool:
    """Check if quiet output mode is active."""
    return _quiet_mode.get()


def set_quiet_mode(enabled: bool) -> None:
    """Set quiet output mode."""
    _quiet_mode.set(enabled)


def get_current_log_path() -> str | None:
    """Get the current command's log file path."""
    return _current_log_path.get()


def set_current_log_path(path: str | None) -> None:
    """Set the current command's log file path."""
    _current_log_path.set(path)


def _get_log_dir() -> str | None:
    """Get the current command's log directory path."""
    return _current_log_dir.get()


def set_current_log_dir(path: str | None) -> None:
    """Set the current command's log directory path."""
    _current_log_dir.set(path)


def format_success(message: str, details: Mapping[str, object] | None = None) -> str:
    """Format success message with optional details.

    Args:
        message: Success message
        details: Optional key-value pairs to display

    Returns:
        Formatted success string
    """
    theme = get_active_theme()
    lines = [theme.apply_success(f"✓ {message}")]
    if details:
        for key, val in details.items():
            lines.append(f"  {secondary(f'{key}:')} {value(str(val))}")
    return "\n".join(lines)


def format_error(message: str, reason: str, suggestions: list[str] | None = None) -> str:
    """Format error message with reason and suggestions.

    Args:
        message: Error message
        reason: Reason for the error
        suggestions: Optional list of suggestions

    Returns:
        Formatted error string
    """
    theme = get_active_theme()
    lines = [
        theme.apply_error(f"✗ {message}"),
        f"  {secondary('Reason:')} {reason}",
    ]
    if suggestions:
        lines.append("")
        lines.append(f"  {secondary('Suggestions:')}")
        for suggestion in suggestions:
            lines.append(f"  • {suggestion}")
    return "\n".join(lines)


def format_info(message: str, details: Mapping[str, object] | None = None) -> str:
    """Format info message with optional details.

    Args:
        message: Info message
        details: Optional key-value pairs to display

    Returns:
        Formatted info string
    """
    theme = get_active_theme()
    lines = [theme.apply_info(f"• {message}")]
    if details:
        for key, val in details.items():
            lines.append(f"  {secondary(f'{key}:')} {value(str(val))}")
    return "\n".join(lines)


def echo_success(message: str, details: Mapping[str, object] | None = None) -> None:
    """Format and echo success message with optional details.

    Args:
        message: Success message
        details: Optional key-value pairs to display
    """
    log_path = get_current_log_path()
    if is_quiet_mode():
        _echo_success_quiet(log_path)
    elif is_json_mode():
        json_success(details, log_path=log_path, log_dir=_get_log_dir())
    elif is_verbose_mode():
        _echo_success_verbose(message, details, log_path)
    else:
        _echo_success_default(details, log_path)


def _echo_success_quiet(log_path: str | None) -> None:
    """Output success in quiet mode — log_dir only."""
    log_dir = _get_log_dir()
    if log_dir:
        click.echo(f"log_dir: {log_dir}", file=get_cli_stdout())
    elif log_path:
        click.echo(f"log_dir: {log_path}", file=get_cli_stdout())


def _echo_success_verbose(message: str, details: Mapping[str, object] | None, log_path: str | None) -> None:
    """Output success in verbose mode — formatted with styling."""
    out = get_cli_stdout()
    click.echo(format_success(message, details), file=out)
    log_dir = _get_log_dir()
    if log_dir:
        click.echo(f"  {secondary('log_dir:')} {value(log_dir)}", file=out)
    elif log_path:
        click.echo(f"  {secondary('log_dir:')} {value(log_path)}", file=out)


def _echo_success_default(details: Mapping[str, object] | None, log_path: str | None) -> None:
    """Output success in default mode — YAML-like compact."""
    out = get_cli_stdout()
    click.echo("status: success", file=out)
    if details:
        for key, val in details.items():
            click.echo(f"{key}: {val}", file=out)
    log_dir = _get_log_dir()
    if log_dir:
        click.echo(f"log_dir: {log_dir}", file=out)
    elif log_path:
        click.echo(f"log_dir: {log_path}", file=out)


def _append_error_to_log(log_path: str | None, error_code: ErrorCode, message: str, suggestions: list[str]) -> None:
    """Append error details to the log file so errors are captured even in non-verbose mode."""
    if not log_path:
        return
    try:
        with open(log_path, "a") as f:
            f.write("\n--- ERROR ---\n")
            f.write(f"code: {error_code.value}\n")
            f.write(f"message: {message}\n")
            if suggestions:
                f.write("suggestions:\n")
                for s in suggestions:
                    f.write(f"  - {s}\n")
    except Exception:  # noqa: BLE001
        pass  # Never mask the real error


def exit_with_error(
    title: str,
    message: str,
    suggestions: list[str],
    error_code: ErrorCode = ErrorCode.UNEXPECTED_ERROR,
    retryable: bool = False,
    details: Mapping[str, object] | None = None,
) -> NoReturn:
    """Display formatted error and exit with error code."""
    log_path = get_current_log_path()
    out = get_cli_stdout()
    _append_error_to_log(log_path, error_code, message, suggestions)
    if is_quiet_mode():
        _exit_error_quiet(out, log_path)
    elif is_json_mode():
        _exit_error_json(error_code, message, retryable, log_path, details)
    elif is_verbose_mode():
        _exit_error_verbose(out, title, message, suggestions, details, log_path)
    else:
        _exit_error_default(out, error_code, message, retryable, suggestions, details, log_path)
    raise click.exceptions.Exit(EXIT_CODE_ERROR)


def _exit_error_quiet(out: TextIO, log_path: str | None) -> None:
    """Output error in quiet mode — log_dir only."""
    log_dir = _get_log_dir()
    if log_dir:
        click.echo(f"log_dir: {log_dir}", file=out)
    elif log_path:
        click.echo(f"log_dir: {log_path}", file=out)


def _exit_error_json(
    error_code: ErrorCode,
    message: str,
    retryable: bool,
    log_path: str | None,
    details: Mapping[str, object] | None,
) -> None:
    """Output error in JSON mode."""
    json_error(error_code, message, retryable=retryable, log_path=log_path, log_dir=_get_log_dir(), details=details)


def _exit_error_verbose(
    out: TextIO,
    title: str,
    message: str,
    suggestions: list[str],
    details: Mapping[str, object] | None,
    log_path: str | None,
) -> None:
    """Output error in verbose mode — formatted with styling."""
    click.echo(format_error(title, message, suggestions=suggestions), file=out)
    if details:
        for key, val in details.items():
            click.echo(f"  {secondary(f'{key}:')} {value(str(val))}", file=out)
    if log_path:
        click.echo(f"  {secondary('log_dir:')} {value(log_path)}", file=out)


def _exit_error_default(
    out: TextIO,
    error_code: ErrorCode,
    message: str,
    retryable: bool,
    suggestions: list[str],
    details: Mapping[str, object] | None,
    log_path: str | None,
) -> None:
    """Output error in default mode — YAML-like compact."""
    click.echo("status: error", file=out)
    click.echo(f"code: {error_code.value}", file=out)
    click.echo(f"message: {message}", file=out)
    click.echo(f"retryable: {str(retryable).lower()}", file=out)
    if details:
        for key, val in details.items():
            click.echo(f"{key}: {val}", file=out)
    if suggestions:
        click.echo("suggestions:", file=out)
        for s in suggestions:
            click.echo(f"  - {s}", file=out)
    if log_path:
        click.echo(f"log_dir: {log_path}", file=out)
