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
"""Validation and error handling utilities for browser CLI commands."""

from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from nova_act.cli.browser.services.session.manager import SessionManager

from nova_act.cli.core.json_output import ErrorCode
from nova_act.cli.core.output import exit_with_error

# Protocols accepted across all URL validation functions
VALID_URL_PREFIXES = ("http://", "https://", "about:", "app://")

__all__ = [
    "VALID_URL_PREFIXES",
    "validate_url_format",
    "warn_missing_protocol",
    "require_argument",
    "validate_prompt",
    "validate_session_available",
    "validate_starting_page",
]


def validate_url_format(url: str, param_name: str = "URL") -> None:
    """Validate URL has proper protocol format."""
    if not url.startswith(VALID_URL_PREFIXES):
        exit_with_error(
            f"Invalid {param_name} format: {url}",
            f"{param_name} must include protocol (http:// or https://)",
            suggestions=[f"Try: https://{url}", "Example: https://example.com"],
            error_code=ErrorCode.VALIDATION_ERROR,
        )


def warn_missing_protocol(url: str) -> None:
    """Warn if URL is missing a recognized protocol prefix."""
    if not url.startswith(VALID_URL_PREFIXES):
        prefix_list = ", ".join(VALID_URL_PREFIXES)
        click.echo(
            click.style(
                f"⚠ Warning: URL '{url}' does not start with a recognized protocol ({prefix_list})",
                fg="yellow",
            )
        )


def require_argument(value: str | None, param_name: str, example: str) -> None:
    """Validate that a required argument is provided."""
    if not value:
        exit_with_error(
            f"Missing {param_name} argument",
            f"{param_name} is required",
            suggestions=[
                f"Provide a {param_name}: {example}",
                "Include protocol (http:// or https://)" if "URL" in param_name else f"Example: {example}",
            ],
            error_code=ErrorCode.VALIDATION_ERROR,
        )


def validate_prompt(prompt: str) -> None:
    """Validate prompt is non-empty.

    Args:
        prompt: The prompt string to validate

    Raises:
        click.exceptions.Exit: If prompt is empty or whitespace-only
    """
    if not prompt.strip():
        exit_with_error(
            "Empty prompt",
            "Prompt cannot be empty",
            suggestions=[
                "Provide a meaningful action: act browser execute 'Click the submit button'",
                "Example: act browser execute 'Extract the page title'",
            ],
            error_code=ErrorCode.VALIDATION_ERROR,
        )


def validate_session_available(session_id: str, manager: "SessionManager") -> None:
    """Validate that a session ID is available for creation.

    Args:
        session_id: ID to validate
        manager: SessionManager instance

    Raises:
        click.exceptions.Exit: If session already exists
    """
    if manager.session_exists(session_id):
        exit_with_error(
            f"Session '{session_id}' already exists",
            "Cannot create a session with an existing ID",
            suggestions=[
                "Use a different session ID: --session-id <unique-id>",
                f"Close existing session: act browser session close {session_id}",
                "List active sessions: act browser session list",
            ],
            error_code=ErrorCode.SESSION_EXISTS,
        )


def validate_starting_page(starting_page: str | None) -> None:
    """Validate starting page URL format if provided.

    Args:
        starting_page: Optional starting page URL

    Raises:
        click.exceptions.Exit: If starting page format is invalid
    """
    if starting_page:
        validate_url_format(starting_page, "Starting page")
