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
"""Goto command for browser CLI — raw Playwright navigation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from nova_act.cli.browser.services.browser_actions import BrowserActions
from nova_act.cli.browser.utils.decorators import (
    browser_command_options,
    pack_command_params,
)
from nova_act.cli.browser.utils.error_handlers import handle_common_errors
from nova_act.cli.browser.utils.session import (
    command_session,
    get_active_page,
    prepare_session,
)
from nova_act.cli.browser.utils.validation_utils import (
    require_argument,
    warn_missing_protocol,
)
from nova_act.cli.core.output import echo_success

if TYPE_CHECKING:
    from nova_act.cli.browser.types import CommandParams


def _validate_url(url: str | None) -> str:
    """Validate and prepare URL for navigation."""
    require_argument(url, "URL", "act browser goto https://example.com")
    if url is None:
        raise ValueError("URL is required")
    warn_missing_protocol(url)
    return url


@click.command()
@click.argument("url", required=False)
@click.option("--timeout", type=int, help="Navigation timeout in seconds (default: 30)")
@browser_command_options
@handle_common_errors
@pack_command_params
def goto(
    url: str | None,
    timeout: int | None,
    params: CommandParams,
) -> None:
    """Navigate to a URL (raw Playwright go_to_url).

    Examples:
        act browser goto https://amazon.com
        act browser goto https://example.com --session-id my-session
        act browser goto https://example.com --timeout 60
    """
    validated_url = _validate_url(url)
    prep = prepare_session(params, validated_url)

    with command_session(
        "goto", prep.manager, prep.session_info, params, log_args={"url": validated_url, "timeout": timeout}
    ) as nova_act:
        actions = BrowserActions(nova_act)
        actions.goto(validated_url, timeout=timeout)
        title = get_active_page(nova_act, prep.session_info).title()

    echo_success(
        f"Navigated to {validated_url}",
        details={"URL": validated_url, "Title": title},
    )
