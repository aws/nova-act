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
"""Browser configuration utilities for browser CLI commands."""

import os
from dataclasses import dataclass

from nova_act.cli.core.output import exit_with_error

# Constants
MILLISECONDS_PER_SECOND = 1000
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_SCREENSHOT_QUALITY = 80


@dataclass(frozen=True)
class ScreenshotConfig:
    """Typed configuration for Playwright page.screenshot() calls.

    Attributes:
        output_format: Image format ('png' or 'jpeg').
        full_page: Whether to capture full page or viewport only.
        quality: JPEG quality (0-100), only set for JPEG format.
    """

    output_format: str
    full_page: bool
    quality: int | None = None

    def to_kwargs(self) -> dict[str, object]:
        """Convert to kwargs dict for page.screenshot()."""
        kwargs: dict[str, object] = {"type": self.output_format, "full_page": self.full_page}
        if self.quality is not None:
            kwargs["quality"] = self.quality
        return kwargs


def _validate_headless_flags(headless_flag: bool, headed_flag: bool) -> None:
    """Validate that headless and headed flags are not both set."""
    if headless_flag and headed_flag:
        exit_with_error(
            "Conflicting flags",
            "Cannot use both --headless and --headed",
            suggestions=["Use only one: --headless OR --headed"],
        )


def _resolve_from_cli_flags(headless_flag: bool, headed_flag: bool) -> bool | None:
    """Resolve headless mode from CLI flags, returning None if neither is set."""
    if headless_flag:
        return True
    if headed_flag:
        return False
    return None


def _resolve_from_environment() -> bool | None:
    """Resolve headless mode from NOVA_ACT_HEADLESS environment variable.

    Returns:
        True if env var is truthy, False if falsy, None if not set.
    """
    env_headless = os.getenv("NOVA_ACT_HEADLESS", "").strip().lower()
    if not env_headless:
        return None
    return env_headless in ("true", "1", "yes")


def determine_headless_mode(headless_flag: bool, headed_flag: bool) -> bool:
    """Determine effective headless mode with precedence: CLI flags > env > default.

    Precedence:
    1. CLI flags (--headless or --headed)
    2. NOVA_ACT_HEADLESS environment variable
    3. Default: True (headless mode for agent workflows)

    Args:
        headless_flag: Value of --headless flag
        headed_flag: Value of --headed flag

    Returns:
        True for headless mode, False for headed mode
    """
    _validate_headless_flags(headless_flag, headed_flag)

    cli_result = _resolve_from_cli_flags(headless_flag, headed_flag)
    if cli_result is not None:
        return cli_result

    env_result = _resolve_from_environment()
    if env_result is not None:
        return env_result

    return True


def convert_timeout_to_ms(timeout: int | None) -> int:
    """Convert timeout from seconds to milliseconds, using default if None."""
    if timeout is not None:
        return timeout * MILLISECONDS_PER_SECOND
    return DEFAULT_TIMEOUT_SECONDS * MILLISECONDS_PER_SECOND


def build_screenshot_kwargs(
    output_format: str,
    full_page: bool,
    quality: int,
) -> ScreenshotConfig:
    """Build screenshot config for Playwright page.screenshot() call.

    Args:
        output_format: Image format ('png' or 'jpeg')
        full_page: Whether to capture full page or viewport only
        quality: JPEG quality (0-100), only used for JPEG format

    Returns:
        ScreenshotConfig dataclass with typed fields.
    """
    return ScreenshotConfig(
        output_format=output_format,
        full_page=full_page,
        quality=quality if output_format == "jpeg" else None,
    )
