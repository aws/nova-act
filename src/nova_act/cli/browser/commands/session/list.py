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
"""Session list command and display helpers."""

import click

from nova_act.cli.browser.services.session.manager import filter_active_sessions
from nova_act.cli.browser.services.session.models import SessionInfo
from nova_act.cli.browser.utils.decorators import json_option
from nova_act.cli.browser.utils.session import get_session_manager
from nova_act.cli.core.constants import DEFAULT_DATETIME_FORMAT
from nova_act.cli.core.json_output import is_json_mode
from nova_act.cli.core.output import echo_success, exit_with_error


def _format_session_details(sessions: list[SessionInfo]) -> dict[str, str]:
    """Format session information for human-readable display.

    Args:
        sessions: List of sessions to format

    Returns:
        Dictionary mapping session labels to formatted details
    """
    details = {}
    for session in sessions:
        parts = [session.state.value, f"Created: {session.created_at.strftime(DEFAULT_DATETIME_FORMAT)}"]
        if session.last_used:
            parts.append(f"Last used: {session.last_used.strftime(DEFAULT_DATETIME_FORMAT)}")
        details[f"Session '{session.session_id}'"] = " | ".join(parts)
    return details


def _display_empty_sessions(show_all: bool) -> None:
    """Display message when no sessions exist."""
    status_msg = "No sessions" if show_all else "No active browser sessions"
    if is_json_mode():
        echo_success(status_msg, details={"sessions": []})
    else:
        echo_success(status_msg, details={"Info": "Use 'act browser session create <url>' to start a session"})


def _display_sessions(sessions: list[SessionInfo], show_all: bool) -> None:
    """Display formatted session list."""
    status_msg = f"Sessions ({len(sessions)})" if show_all else f"Active browser sessions ({len(sessions)})"
    if is_json_mode():
        echo_success(status_msg, details={"sessions": [s.to_dict() for s in sessions]})
    else:
        echo_success(status_msg, details=_format_session_details(sessions))


@click.command(name="list")
@click.option("--all", "show_all", is_flag=True, help="Show all sessions including stopped/failed")
@json_option
def list_sessions(show_all: bool) -> None:
    """List active browser sessions.

    By default, only shows active sessions (STARTING, STARTED).
    Use --all to show all sessions including stopped/failed.

    Examples:
        act browser session list
        act browser session list --all
    """
    manager = get_session_manager()

    try:
        sessions = manager.list_sessions()

        if not show_all:
            sessions = filter_active_sessions(sessions)

        if not sessions:
            _display_empty_sessions(show_all)
            return

        _display_sessions(sessions, show_all)

    except Exception as e:
        exit_with_error(
            "Failed to list sessions", str(e), suggestions=["Check if session manager is accessible", "Try again"]
        )
