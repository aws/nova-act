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
"""Session management utilities for browser CLI commands."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

import click

from nova_act import NovaAct
from nova_act.cli.browser.services.session.manager import SessionManager
from nova_act.cli.browser.services.session.models import (
    BrowserOptions,
    SessionInfo,
)
from nova_act.cli.browser.services.step_tracking import (
    patch_nova_act_for_step_snapshots,
)
from nova_act.cli.browser.utils.auth import AuthConfig, resolve_auth_mode
from nova_act.cli.browser.utils.browser_config_cli import determine_headless_mode
from nova_act.cli.browser.utils.disk_usage import check_disk_usage
from nova_act.cli.browser.utils.log_capture import (
    capture_command_log,
    capture_failure_screenshot,
    get_current_command_dir,
)
from nova_act.cli.browser.utils.nova_args import (
    filter_constructor_args,
    filter_method_args,
    parse_nova_args,
)
from nova_act.cli.core.config import get_browser_cli_dir
from nova_act.cli.core.exceptions import SessionNotFoundError

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from nova_act.cli.browser.services.intent_resolution.snapshot import SnapshotElement
    from nova_act.cli.browser.types import CommandParams

logger = logging.getLogger(__name__)


@dataclass
class PreparedSession:
    """Result of preparing a session for command execution.

    Attributes:
        session_info: The active or newly created session.
        method_args: Parsed nova method-level arguments.
        manager: The SessionManager instance managing this session.
    """

    session_info: SessionInfo
    method_args: dict[str, object] = field(default_factory=dict)
    manager: SessionManager = field(default_factory=SessionManager)


def get_or_create_session(
    manager: SessionManager,
    session_id: str,
    starting_page: str | None,
    browser_options: BrowserOptions,
    max_sessions: int | None = None,
) -> SessionInfo:
    """Get existing session or create new one with given parameters."""
    # Try to recover an existing session.
    try:
        session_info = manager.get_session(session_id, auth_config=browser_options.auth_config)
    except SessionNotFoundError:
        session_info = None

    # Reuse if the session has a live NovaAct instance.
    if session_info is not None and session_info.nova_act_instance:
        return session_info

    # Session is missing or stale — clean up and create a new one.
    try:
        manager.close_session(session_id, force=True)
    except SessionNotFoundError:
        pass
    return manager.create_session(
        session_id,
        starting_page=starting_page or "about:blank",
        browser_options=browser_options,
        max_sessions=max_sessions,
    )


def build_browser_options_from_params(
    params: "CommandParams",
    *,
    nova_args: dict[str, object] | None = None,
    auth_config: AuthConfig | None = None,
) -> BrowserOptions:
    """Build BrowserOptions from a CommandParams object.

    Args:
        params: CLI parameters containing browser configuration.
        nova_args: Pre-parsed nova args dict. If None, parses from params.nova_arg.
        auth_config: Resolved authentication configuration.
    """
    effective_headless = determine_headless_mode(params.headless, params.headed)
    resolved_nova_args = nova_args if nova_args is not None else parse_nova_args(params.nova_arg)
    if params.ignore_https_errors and "ignore_https_errors" not in resolved_nova_args:
        resolved_nova_args["ignore_https_errors"] = True

    return BrowserOptions(
        headless=effective_headless,
        headed=params.headed,
        executable_path=params.executable_path,
        profile_path=params.profile_path,
        ignore_https_errors=params.ignore_https_errors,
        nova_args=resolved_nova_args,
        launch_args=list(params.launch_arg),
        auth_config=auth_config,
        use_default_chrome=params.use_default_chrome,
        user_data_dir=params.user_data_dir,
        cdp_endpoint_url=params.cdp,
    )


def get_nova_act_instance(session_info: SessionInfo) -> NovaAct:
    """Get NovaAct instance from session, raising error if unavailable."""
    if not session_info.nova_act_instance:
        raise RuntimeError("NovaAct instance not available")
    return session_info.nova_act_instance


def get_active_page(nova_act: NovaAct, session_info: SessionInfo) -> Page:
    """Return the Playwright page for the active tab.

    Uses session_info.active_tab_index to look up the correct page from
    the browser context. Falls back to nova_act.page if the index is out
    of bounds (e.g., tabs were closed between invocations).

    Args:
        nova_act: NovaAct instance with a live browser context.
        session_info: Session info containing the persisted active_tab_index.

    Returns:
        Playwright Page object for the selected tab.
    """
    try:
        pages = nova_act.page.context.pages
        idx = session_info.active_tab_index
        if 0 <= idx < len(pages):
            return pages[idx]
    except Exception:
        pass
    return nova_act.page


def patch_active_tab(nova_act: NovaAct, session_info: SessionInfo) -> None:
    """Monkeypatch SDK page resolution to respect CLI tab selection.

    When active_tab_index != 0, patches the actuator's get_page() so that
    index == -1 returns the selected tab instead of the last-created page.
    This makes AI commands (act, ask, execute, navigate, explore, etc.)
    operate on the tab chosen via tab-select.

    Safe: each CLI invocation is a fresh process, so the patch is isolated.
    """
    idx = session_info.active_tab_index
    if idx == 0:
        return  # Default behavior — no patch needed

    try:
        pm = nova_act._actuator._playwright_manager  # type: ignore[attr-defined]
    except AttributeError:
        logger.debug("Cannot patch active tab: actuator has no _playwright_manager")
        return

    original_get_page = pm.get_page

    def patched_get_page(index: int):  # type: ignore[no-untyped-def]
        if index == -1:
            try:
                pages = pm.context.pages
                if 0 <= idx < len(pages):
                    return pages[idx]
            except Exception:
                pass
        return original_get_page(index)

    pm.get_page = patched_get_page


def get_session_manager() -> SessionManager:
    """Get SessionManager instance for managing browser sessions."""
    return SessionManager()


@contextmanager
def locked_session(manager: SessionManager, session_info: SessionInfo, session_id: str) -> Iterator[NovaAct]:
    """Context manager that acquires session lock and provides NovaAct instance.

    Args:
        manager: SessionManager instance that owns the session state
        session_info: Session information object
        session_id: Session identifier for lock acquisition

    Yields:
        NovaAct instance for the locked session

    Raises:
        SessionLockTimeout: If lock cannot be acquired
        RuntimeError: If NovaAct instance is not available
    """
    with manager.with_session_lock(session_id):
        nova_act = get_nova_act_instance(session_info)
        yield nova_act
        # nova_act.stop() is intentionally NOT called here. The CLI uses a
        # stateless subprocess model where each command is a fresh process.
        # On process exit the OS closes the CDP WebSocket and Chrome releases
        # the DevTools session. Verified empirically: 30 rapid-fire iterations
        # without stop() produced 0 failures and no target accumulation.
        # Calling stop() would add teardown latency and hang risk with no
        # measurable stability benefit.


from nova_act.cli.browser.utils.orientation import (  # noqa: E402 — deferred import
    auto_orientation,
    emit_observe,
    emit_steps_summary,
)


def _handle_post_command(
    nova_act: NovaAct,
    session_info: SessionInfo,
    params: "CommandParams",
    command_name: str,
    cmd_start: datetime,
    step_snapshots: list[list[SnapshotElement]],
    log_args: dict[str, object] | None,
) -> None:
    """Handle post-yield logic: observe, orientation, steps summary, stdout emission, and session recording."""
    if params.observe:
        emit_observe(nova_act)

    # Auto-orientation: snapshot + screenshot after every command
    orientation = auto_orientation(nova_act, session_info, params, command_name)

    # Steps summary: parse trajectory + merge monkey-patch snapshots
    steps_meta = emit_steps_summary(nova_act, params, command_name, step_snapshots)
    if steps_meta:
        orientation.update(steps_meta)

    # Auto-record command to session manifest
    try:
        from nova_act.cli.browser.services.session_recorder import get_recorder

        duration_ms = (datetime.now() - cmd_start).total_seconds() * 1000
        recorder = get_recorder(params.session_id)
        recorder.record_step(
            command_name=command_name,
            args=log_args,
            started_at=cmd_start,
            duration_ms=duration_ms,
            screenshots=(
                {k: str(v) for k, v in orientation.items() if k in ("screenshot_path", "snapshot_path")}
                if orientation
                else None
            ),
            steps_file=str(steps_meta.get("steps_path")) if steps_meta and steps_meta.get("steps_path") else None,
        )
    except Exception:
        logger.debug("Session recording failed for command '%s'", command_name)


@contextmanager
def command_session(
    command_name: str,
    manager: SessionManager,
    session_info: SessionInfo,
    params: "CommandParams",
    log_args: dict[str, object] | None = None,
) -> Iterator[NovaAct]:
    """Unified context manager combining log capture, session locking, and auto-screenshot.

    Replaces the duplicated nested pattern::

        with capture_command_log(...) as _:
            with locked_session(...) as nova_act:
                ...

    On unhandled exceptions, automatically captures a failure screenshot (unless
    ``params.no_screenshot_on_failure`` is set) and attaches the path to the
    exception as ``_failure_screenshot``.

    Args:
        command_name: CLI command name for log file (e.g. "ask", "screenshot")
        manager: SessionManager instance that owns the session state
        session_info: Session information object
        params: Shared CLI parameters (provides session_id, quiet, verbose, no_screenshot_on_failure)
        log_args: Optional command arguments to record in log metadata

    Yields:
        NovaAct instance for the locked session
    """
    with capture_command_log(
        command_name,
        session_id=params.session_id,
        args=log_args,
        quiet=params.quiet,
        verbose=params.verbose,
    ):
        with locked_session(manager, session_info, params.session_id) as nova_act:
            # Patch SDK page resolution to respect tab-select
            patch_active_tab(nova_act, session_info)

            # Capture before-screenshot for visual history
            if not params.no_screenshot:
                try:
                    cmd_dir = get_current_command_dir()
                    if cmd_dir is not None:
                        cmd_dir.mkdir(parents=True, exist_ok=True)
                        before_path = cmd_dir / "before.png"
                        get_active_page(nova_act, session_info).screenshot(path=str(before_path))
                except Exception:
                    logger.debug("Before-screenshot failed for command '%s'", command_name)

            # Monkey-patch for per-step a11y snapshots
            step_snapshots: list[list[SnapshotElement]] = []
            patch_nova_act_for_step_snapshots(nova_act, step_snapshots)

            _cmd_start = datetime.now()
            try:
                yield nova_act
            except Exception as exc:
                if not params.no_screenshot_on_failure:
                    screenshot_path = capture_failure_screenshot(nova_act, params.session_id, command_name)
                    if screenshot_path:
                        exc._failure_screenshot = screenshot_path  # type: ignore[attr-defined]
                raise
            else:
                _handle_post_command(
                    nova_act,
                    session_info,
                    params,
                    command_name,
                    _cmd_start,
                    step_snapshots,
                    log_args,
                )


def prepare_session(
    params: "CommandParams",
    starting_page: str | None,
) -> PreparedSession:
    """Parse nova args, prepare browser options, and get or create a session.

    Args:
        params: Shared CLI parameters packed by @pack_command_params.
        starting_page: Starting URL for new sessions (command-specific).

    Returns:
        PreparedSession with session info, method args, and manager.
    """
    nova_args = parse_nova_args(params.nova_arg)
    constructor_args = filter_constructor_args(nova_args)
    method_args = filter_method_args(nova_args)

    auth_config = resolve_auth_mode(params.auth_mode, params.profile, params.region, params.workflow_name)
    browser_options = build_browser_options_from_params(
        params,
        nova_args=constructor_args,
        auth_config=auth_config,
    )

    manager = get_session_manager()
    session_info = get_or_create_session(manager, params.session_id, starting_page, browser_options)

    _emit_disk_warning()

    return PreparedSession(session_info=session_info, method_args=method_args, manager=manager)


def _emit_disk_warning() -> None:
    """Check disk usage and emit warning to stderr if over threshold."""
    warning = check_disk_usage(get_browser_cli_dir())
    if warning:
        click.echo(warning, err=True)
