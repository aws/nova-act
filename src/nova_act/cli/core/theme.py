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
"""Theme system for Nova Act CLI styling."""

from enum import Enum
from logging import getLogger
from typing import Protocol

import click

logger = getLogger(__name__)


class ThemeName(str, Enum):
    """Available theme names."""

    DEFAULT = "default"
    MINIMAL = "minimal"
    NONE = "none"


class Theme(Protocol):
    """Protocol defining theme interface."""

    enabled: bool

    def apply_info(self, text: str) -> str: ...
    def apply_success(self, text: str) -> str: ...
    def apply_error(self, text: str) -> str: ...
    def apply_warning(self, text: str) -> str: ...
    def apply_header(self, text: str) -> str: ...
    def apply_value(self, text: str) -> str: ...
    def apply_secondary(self, text: str) -> str: ...
    def apply_command(self, text: str) -> str: ...


class DefaultTheme:
    """Default color theme matching current CLI appearance."""

    enabled: bool = True

    def apply_info(self, text: str) -> str:
        return text

    def apply_success(self, text: str) -> str:
        return click.style(text, fg="bright_green", bold=True)

    def apply_error(self, text: str) -> str:
        return click.style(text, fg="bright_red", bold=True)

    def apply_warning(self, text: str) -> str:
        return click.style(text, fg="bright_yellow", bold=True)

    def apply_header(self, text: str) -> str:
        return click.style(text, fg="blue", bold=True)

    def apply_value(self, text: str) -> str:
        return click.style(text, fg="white")

    def apply_secondary(self, text: str) -> str:
        return click.style(text, dim=True)

    def apply_command(self, text: str) -> str:
        return click.style(text, dim=True)


class MinimalTheme:
    """Minimal theme with reduced colors."""

    enabled: bool = True

    def apply_info(self, text: str) -> str:
        return text

    def apply_success(self, text: str) -> str:
        return click.style(text, bold=True)

    def apply_error(self, text: str) -> str:
        return click.style(text, bold=True)

    def apply_warning(self, text: str) -> str:
        return text

    def apply_header(self, text: str) -> str:
        return click.style(text, bold=True)

    def apply_value(self, text: str) -> str:
        return text

    def apply_secondary(self, text: str) -> str:
        return click.style(text, dim=True)

    def apply_command(self, text: str) -> str:
        return text


class NoTheme:
    """No styling theme for automation/scripting."""

    enabled: bool = False

    def apply_info(self, text: str) -> str:
        return text

    def apply_success(self, text: str) -> str:
        return text

    def apply_error(self, text: str) -> str:
        return text

    def apply_warning(self, text: str) -> str:
        return text

    def apply_header(self, text: str) -> str:
        return text

    def apply_value(self, text: str) -> str:
        return text

    def apply_secondary(self, text: str) -> str:
        return text

    def apply_command(self, text: str) -> str:
        return text


_THEMES: dict[ThemeName, Theme] = {
    ThemeName.DEFAULT: DefaultTheme(),
    ThemeName.MINIMAL: MinimalTheme(),
    ThemeName.NONE: NoTheme(),
}

_active_theme: Theme = _THEMES[ThemeName.DEFAULT]


def get_theme(name: str | ThemeName) -> Theme:
    """Get theme by name."""
    if isinstance(name, str):
        try:
            name = ThemeName(name)
        except ValueError:
            logger.warning(f"Invalid theme name '{name}', falling back to default theme")
            name = ThemeName.DEFAULT
    return _THEMES[name]


def set_active_theme(theme_name: ThemeName) -> None:
    """Set the active theme by name."""
    global _active_theme
    _active_theme = _THEMES[theme_name]


def get_active_theme() -> Theme:
    """Get the currently active theme."""
    return _active_theme
