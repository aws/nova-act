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
"""Timeout context managers for browser CLI commands."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from nova_act import NovaAct

from nova_act.cli.browser.utils.browser_config_cli import convert_timeout_to_ms

DEFAULT_TIMEOUT_MS = 30_000


@contextmanager
def temporary_timeout(nova_act: NovaAct, timeout: int | None) -> Iterator[None]:
    """Temporarily set page timeout, restoring default afterward."""
    if timeout is None:
        yield
        return
    nova_act.page.set_default_timeout(convert_timeout_to_ms(timeout))
    try:
        yield
    finally:
        nova_act.page.set_default_timeout(DEFAULT_TIMEOUT_MS)


@contextmanager
def temporary_navigation_timeout(nova_act: NovaAct, timeout: int | None) -> Iterator[None]:
    """Temporarily set navigation timeout, restoring default afterward."""
    if timeout is None:
        yield
        return
    nova_act.page.set_default_navigation_timeout(convert_timeout_to_ms(timeout))
    try:
        yield
    finally:
        nova_act.page.set_default_navigation_timeout(DEFAULT_TIMEOUT_MS)
