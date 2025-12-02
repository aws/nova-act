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
"""Styling utilities for Nova Act CLI using Click's built-in styling."""

import os
from logging import getLogger

import click

from nova_act.cli.core.constants import DEFAULT_THEME, THEME_ENV_VAR
from nova_act.cli.core.theme import ThemeName, get_active_theme, set_active_theme
from nova_act.cli.core.user_config_manager import UserConfigManager

logger = getLogger(__name__)


def _initialize_theme() -> None:
    """Initialize theme from config or environment."""
    env_theme = os.environ.get(THEME_ENV_VAR)
    if env_theme:
        try:
            theme_name = ThemeName(env_theme)
        except ValueError:
            logger.warning(f"Invalid theme in environment variable '{env_theme}', falling back to default")
            theme_name = ThemeName.DEFAULT
        set_active_theme(theme_name)
        return

    try:
        config = UserConfigManager.get_config()
        if not config.theme.enabled:
            set_active_theme(ThemeName.NONE)
        else:
            try:
                theme_name = ThemeName(config.theme.name)
            except ValueError:
                logger.warning(f"Invalid theme in config '{config.theme.name}', falling back to default")
                theme_name = ThemeName.DEFAULT
            set_active_theme(theme_name)
    except Exception:
        set_active_theme(DEFAULT_THEME)


_initialize_theme()


def info(message: str) -> None:
    """Print info message."""
    click.echo(get_active_theme().apply_info(message))


def success(message: str) -> None:
    """Print success message."""
    click.echo(get_active_theme().apply_success(message))


def warning(message: str) -> None:
    """Print warning message."""
    click.echo(get_active_theme().apply_warning(message))


def error(message: str) -> None:
    """Print error message."""
    click.echo(get_active_theme().apply_error(message))


def header(text: str) -> str:
    """Style text as section header."""
    return get_active_theme().apply_header(text)


def value(text: str) -> str:
    """Style important values (names, ARNs, etc)."""
    return get_active_theme().apply_value(text)


def secondary(text: str) -> str:
    """Style secondary information (timestamps, paths, etc)."""
    return get_active_theme().apply_secondary(text)


def command(text: str) -> str:
    """Style command examples."""
    return get_active_theme().apply_command(text)


def styled_error_exception(message: str) -> click.ClickException:
    """Create a ClickException with styled error message."""
    return click.ClickException(get_active_theme().apply_error(message))
