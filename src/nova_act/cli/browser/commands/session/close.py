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
"""Session close and close-all commands."""

import click

from nova_act.cli.browser.services.session.closer import SessionCloser
from nova_act.cli.browser.services.session.manager import SessionManager
from nova_act.cli.browser.services.session.models import SessionInfo
from nova_act.cli.browser.utils.decorators import json_option
from nova_act.cli.browser.utils.session import get_session_manager
from nova_act.cli.core.exceptions import SessionNotFoundError
from nova_act.cli.core.json_output import ErrorCode
from nova_act.cli.core.output import echo_success, exit_with_error


def _close_single_session(manager: SessionManager, session_id: str, force: bool) -> None:
    """Close a single session with comprehensive error handling.

    Args:
        manager: SessionManager instance
        session_id: ID of session to close
        force: Whether to force close without stopping browser

    Raises:
        click.exceptions.Exit: On any error during session closure
    """
    try:
        manager.close_session(session_id, force=force)
    except SessionNotFoundError:
        exit_with_error(
            f"Session '{session_id}' not found",
            "The specified session does not exist",
            suggestions=["List active sessions: act browser session list", "Check the session ID spelling"],
            error_code=ErrorCode.SESSION_NOT_FOUND,
        )
    except RuntimeError as e:
        exit_with_error(
            f"Failed to close session '{session_id}'",
            str(e),
            suggestions=[
                "Check if the browser is still running",
                "Try again",
                "Use '--force' flag to force close: act browser session close --force <session_id>",
            ],
            error_code=ErrorCode.BROWSER_ERROR,
        )
    except (
        Exception
    ) as e:  # noqa: BLE001 — top-level CLI error boundary; catches anything not handled by specific handlers above
        exit_with_error(
            f"Unexpected error closing session '{session_id}'",
            str(e),
            suggestions=["Try again", "Check system resources"],
            error_code=ErrorCode.UNEXPECTED_ERROR,
        )


def _get_sessions_to_close(manager: SessionManager) -> list[SessionInfo]:
    """Retrieve list of sessions to close.

    Args:
        manager: SessionManager instance

    Returns:
        List of session info objects

    Raises:
        click.exceptions.Exit: If unable to retrieve sessions
    """
    try:
        return manager.list_sessions()
    except (OSError, RuntimeError) as e:
        exit_with_error(
            "Failed to close all sessions",
            str(e),
            suggestions=["Try again", "Close sessions individually: act browser session close <session-id>"],
        )


def _report_close_all_results(closed_ids: list[str], total_count: int, failed_sessions: list[str]) -> None:
    """Report results of closing all sessions."""
    if failed_sessions:
        exit_with_error(
            f"Closed {len(closed_ids)} of {total_count} sessions",
            "Some sessions failed to close",
            suggestions=[
                "Failed sessions:",
                *[f"  - {failure}" for failure in failed_sessions],
                "Try closing failed sessions individually",
            ],
        )
    else:
        echo_success(
            f"Closed all {len(closed_ids)} sessions",
            details={"sessions_closed": closed_ids, "count": len(closed_ids)},
        )


@click.command()
@click.option("--session-id", required=True, help="Session ID to close")
@click.option("--force", is_flag=True, help="Force close without stopping browser (for orphaned sessions)")
@json_option
def close(session_id: str, force: bool) -> None:
    """Close a specific browser session.

    Examples:
        act browser session close --session-id my-session
        act browser session close --session-id default
        act browser session close --session-id orphaned-session --force
    """
    manager = get_session_manager()
    _close_single_session(manager, session_id, force)

    status = "Force closed" if force else "Stopped"
    echo_success(f"Closed session '{session_id}'", details={"Status": status})


@click.command(name="close-all")
@click.option("--force", is_flag=True, help="Force close without stopping browsers")
@json_option
def close_all(force: bool) -> None:
    """Close all active browser sessions.

    Examples:
        act browser session close-all
        act browser session close-all --force
    """
    manager = get_session_manager()
    sessions = _get_sessions_to_close(manager)

    if not sessions:
        echo_success("No sessions to close", details={"Info": "No sessions found"})
        return

    closed_ids, failed_sessions = SessionCloser.close_sessions_batch(manager, sessions, force)
    _report_close_all_results(closed_ids, len(sessions), failed_sessions)
