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
"""Automatic log capture and stdout management for browser CLI commands.

Provides two complementary stdout control mechanisms:
- suppress_sdk_output(): Silences SDK stdout/trace during session setup (no logging).
- capture_command_log(): Captures SDK output to per-command log files during execution.

Both mechanisms suppress the nova_act.trace logger and redirect stdout. They are used
sequentially (suppress during setup, capture during command execution) and should not
be nested.
"""

import io
import logging as _logging
import os
import re
import shutil
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import yaml

from nova_act.cli.core.config import get_log_base_dir
from nova_act.cli.core.output import (
    set_current_log_dir,
    set_current_log_path,
    set_original_stdout,
    set_quiet_mode,
)

LOG_BASE_DIR = get_log_base_dir()
SYSTEM_LOG_DIR = LOG_BASE_DIR / "_system"

_TRACE_LOGGER_NAME = "nova_act.trace"
_SDK_ROOT_LOGGER_NAME = "nova_act"

# SDK loggers that emit noise during session setup but may not yet exist in the
# logger registry (their modules are lazily imported by the SDK).  Explicitly
# creating them via getLogger() before suppression ensures they are captured.
_KNOWN_SDK_LOGGER_NAMES = (
    "nova_act",
    "nova_act.trace",
    "nova_act.nova_act",
    "nova_act.types.workflow",
)

_CMD_DIR_PATTERN = re.compile(r"^\d{8}_\d{6}_\w+$")
_CLI_LOG_SUFFIXES = {".log", ".yaml", ".png", ".txt"}

_current_command_dir: Path | None = None


def get_current_command_dir() -> Path | None:
    """Get the per-command subdirectory for the currently executing command."""
    return _current_command_dir


def set_current_command_dir(path: Path | None) -> None:
    """Set the per-command subdirectory for the currently executing command."""
    global _current_command_dir
    _current_command_dir = path


def _get_sdk_loggers() -> list[_logging.Logger]:
    """Get all loggers in the nova_act namespace (including children with propagate=False).

    Also pre-creates known SDK loggers that may not yet exist in the registry
    because their modules are lazily imported.  This ensures suppress_sdk_output()
    and capture_command_log() can silence them before the SDK code runs.
    """
    # Pre-create known noisy loggers so they appear in the registry
    for name in _KNOWN_SDK_LOGGER_NAMES:
        _logging.getLogger(name)

    prefix = _SDK_ROOT_LOGGER_NAME + "."
    return [
        _logging.getLogger(name)
        for name in _logging.Logger.manager.loggerDict
        if name == _SDK_ROOT_LOGGER_NAME or name.startswith(prefix)
    ]


@contextmanager
def suppress_sdk_output() -> Iterator[None]:
    """Suppress SDK stdout/stderr output (trace logs, thinker dots, workflow messages) during SDK calls.

    Used during session setup where no log file capture is needed.
    For command execution, use capture_command_log() instead.

    SDK loggers use propagate=False with their own StreamHandlers, so we must
    set levels on ALL child loggers, not just the root nova_act logger.
    """
    sdk_loggers = _get_sdk_loggers()
    old_levels = [(logger, logger.level) for logger in sdk_loggers]
    for logger in sdk_loggers:
        logger.setLevel(_logging.CRITICAL)
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    devnull = open(os.devnull, "w")  # noqa: SIM115
    try:
        sys.stdout = devnull
        sys.stderr = devnull
        yield
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        devnull.close()
        for logger, level in old_levels:
            logger.setLevel(level)


def get_log_dir(session_id: str | None) -> Path:
    """Get log directory for a session (or _system for session-less commands)."""
    if session_id:
        return LOG_BASE_DIR / session_id
    return SYSTEM_LOG_DIR


def _build_command_dir(session_id: str | None, command_name: str) -> Path:
    """Build per-command subdirectory: <session_log_dir>/<timestamp>_<command>/"""
    log_dir = get_log_dir(session_id)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    cmd_dir = log_dir / f"{timestamp}_{command_name}"
    cmd_dir.mkdir(parents=True, exist_ok=True)
    return cmd_dir


def _build_log_path(session_id: str | None, command_name: str) -> tuple[Path, Path]:
    """Build log file path: <session_log_dir>/<timestamp>_<command>/log.txt

    Returns:
        Tuple of (log_file_path, command_dir_path).
    """
    cmd_dir = _build_command_dir(session_id, command_name)
    return cmd_dir / "log.txt", cmd_dir


def _write_metadata_header(
    f: io.TextIOWrapper, command_name: str, session_id: str | None, args: dict[str, object] | None
) -> None:
    """Write YAML metadata header to log file."""
    metadata: dict[str, object] = {
        "timestamp": datetime.now().isoformat(),
        "command": command_name,
    }
    if session_id:
        metadata["session_id"] = session_id
    if args:
        metadata["args"] = args
    yaml.dump(metadata, f, default_flow_style=False, sort_keys=False)
    f.write("---\n")
    f.flush()


class _TeeWriter:
    """Writes to a log file and optionally to an original stream."""

    def __init__(self, log_file: io.TextIOWrapper, original: io.TextIOBase | io.TextIOWrapper | None) -> None:
        self.log_file = log_file
        self.original = original

    def write(self, data: str) -> int:
        self.log_file.write(data)
        self.log_file.flush()
        if self.original is not None:
            self.original.write(data)
            self.original.flush()
        return len(data)

    def flush(self) -> None:
        self.log_file.flush()
        if self.original is not None:
            self.original.flush()

    # Support fileno() for compatibility — delegate to original or raise
    def fileno(self) -> int:
        if self.original is not None and hasattr(self.original, "fileno"):
            return self.original.fileno()
        raise io.UnsupportedOperation("fileno")

    def isatty(self) -> bool:
        return False

    def writable(self) -> bool:
        return True


def _patch_stream_handlers(
    logger: _logging.Logger, old_stream: io.TextIOBase | io.TextIOWrapper, new_stream: object
) -> list[tuple[_logging.StreamHandler, io.TextIOBase | io.TextIOWrapper]]:  # type: ignore[type-arg]
    """Update StreamHandlers pointing at old_stream to use new_stream. Returns originals for restore."""
    patched: list[tuple[_logging.StreamHandler, io.TextIOBase | io.TextIOWrapper]] = []  # type: ignore[type-arg]
    for handler in logger.handlers:
        if isinstance(handler, _logging.StreamHandler) and handler.stream is old_stream:
            patched.append((handler, handler.stream))
            handler.stream = new_stream
    return patched


@contextmanager
def capture_command_log(
    command_name: str,
    session_id: str | None = None,
    args: dict[str, object] | None = None,
    quiet: bool = False,
    verbose: bool = False,
) -> Iterator[Path]:
    """Context manager that captures SDK output to a log file.

    Replaces sys.stdout/sys.stderr with _TeeWriter instances to intercept SDK output
    and write it to a per-command log file. CLI output functions bypass the tee via
    set_original_stdout() to write directly to the real terminal.

    Known limitation (RISK-T1, accepted for v1):
        This replaces global sys.stdout/sys.stderr, which is inherently fragile in
        multi-threaded or multi-process contexts. For v1 this is acceptable because:
        - The CLI is single-threaded and single-process
        - The _TeeWriter pattern works correctly in production (every command uses it)
        - Tests use a noop context manager patch to avoid interference with Click's runner
        Future fix: replace stdout/stderr replacement with a logging.FileHandler-based
        approach that captures SDK trace output without touching global streams.

    Note on FileHandler alternative (evaluated and rejected for v1):
        logging.FileHandler on nova_act.trace was considered but rejected because
        the SDK prints directly to stdout (not via the logging module), so a
        FileHandler would miss all SDK output. The TeeWriter approach is required
        until the SDK migrates to proper logging.

    Args:
        command_name: Name of the CLI command (e.g. "execute", "navigate")
        session_id: Session ID (None for session-less commands like doctor)
        args: Command arguments to record in metadata header
        quiet: If True, suppress terminal output (only log file gets SDK trace)
        verbose: If True, show full SDK trace on terminal (decorated mode)

    Yields:
        Path to the log file
    """
    log_path, cmd_dir = _build_log_path(session_id, command_name)
    log_file = open(log_path, "w")  # noqa: SIM115

    _write_metadata_header(log_file, command_name, session_id, args)

    old_stdout = sys.stdout
    old_stderr = sys.stderr

    # Save original stdout so CLI output functions can bypass the tee writer
    set_original_stdout(old_stdout)

    # Set quiet mode so output functions know to emit only log path
    set_quiet_mode(quiet)

    # Determine terminal visibility for stdout
    # Default: suppress SDK trace on terminal (log file only)
    # Verbose: show full SDK trace on terminal
    # Quiet: suppress terminal output (same as default, explicit intent)
    terminal_out = old_stdout if verbose else None
    terminal_err = old_stderr if verbose else None

    tee_out = _TeeWriter(log_file, terminal_out)  # type: ignore[arg-type]
    tee_err = _TeeWriter(log_file, terminal_err)  # type: ignore[arg-type]

    # Capture all SDK loggers and save levels before modifying.
    # SDK loggers use propagate=False with their own StreamHandlers, so we must
    # set levels on ALL child loggers, not just the root nova_act logger.
    sdk_loggers = _get_sdk_loggers()
    old_levels = [(logger, logger.level) for logger in sdk_loggers]
    if not verbose:
        for logger in sdk_loggers:
            logger.setLevel(_logging.CRITICAL)

    sys.stdout = tee_out
    sys.stderr = tee_err

    # Fix stale StreamHandler references: handlers captured sys.stderr at creation
    # time, so replacing stderr doesn't redirect their output to the TeeWriter.
    patched_handlers: list[  # type: ignore[type-arg]
        tuple[_logging.StreamHandler, io.TextIOBase | io.TextIOWrapper]
    ] = []
    for logger in sdk_loggers:
        patched_handlers += _patch_stream_handlers(logger, old_stderr, tee_err)  # type: ignore[arg-type]

    set_current_log_path(str(log_path))
    set_current_log_dir(str(cmd_dir))
    set_current_command_dir(cmd_dir)
    try:
        yield log_path
    finally:
        # NOTE: Do NOT clear log_path here. Commands call echo_success() AFTER
        # exiting command_session(), so the log path must remain available for
        # json_success() / exit_with_error() to include "log" in the output.
        # Each CLI invocation is a separate process, so no state leakage.
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        set_original_stdout(None)
        set_quiet_mode(False)
        for logger, level in old_levels:
            logger.setLevel(level)
        for handler, original_stream in patched_handlers:
            handler.stream = original_stream
        log_file.close()


def build_failure_screenshot_path(session_id: str | None, command_name: str) -> Path:
    """Build path for failure screenshot inside the current command subdirectory."""
    cmd_dir = get_current_command_dir()
    if cmd_dir is not None:
        return cmd_dir / "failure.png"
    # Fallback if called outside capture_command_log context
    fallback_dir = _build_command_dir(session_id, command_name)
    return fallback_dir / "failure.png"


def capture_failure_screenshot(
    nova_act: object,
    session_id: str | None,
    command_name: str,
) -> str | None:
    """Capture a screenshot on failure, returning the saved path or None.

    Args:
        nova_act: NovaAct instance (typed as object to avoid import cycle).
        session_id: Session ID for log directory placement.
        command_name: Command name for the screenshot filename.
    """
    try:
        screenshot_path = build_failure_screenshot_path(session_id, command_name)
        screenshot_bytes = nova_act.page.screenshot()  # type: ignore[attr-defined]
        screenshot_path.write_bytes(screenshot_bytes)
        return str(screenshot_path)
    except Exception:
        return None


def cleanup_session_logs(session_id: str) -> None:
    """Remove CLI-generated log files for a session, preserving SDK artifact subdirectories.

    The SDK writes trajectory JSON and HTML reports into nested <sdk_session_id>/
    subdirectories under the session log dir. CLI commands write into per-command
    subdirectories (e.g. 20260330_155318_execute/). This function deletes CLI command
    subdirectories (matching <timestamp>_<command>/ pattern) while preserving SDK
    artifact subdirectories.
    """
    log_dir = get_log_dir(session_id)
    if not log_dir.exists():
        return

    # Safeguard: only delete within the CLI log base directory
    try:
        log_dir.resolve().relative_to(LOG_BASE_DIR.resolve())
    except ValueError:
        return

    for item in list(log_dir.iterdir()):
        if item.is_dir() and _CMD_DIR_PATTERN.match(item.name):
            # CLI command subdirectory — remove entirely
            shutil.rmtree(item, ignore_errors=True)
        elif item.is_file() and item.suffix in _CLI_LOG_SUFFIXES:
            # Legacy flat files from before per-command subdirs
            item.unlink(missing_ok=True)

    # Remove the session dir only if it's now empty (all SDK subdirs were already gone)
    try:
        log_dir.rmdir()  # only succeeds if empty
    except OSError:
        pass  # subdirectories remain — expected
