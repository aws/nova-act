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
"""Scroll-to command — scroll to a target section on the current page."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

import click

from nova_act.cli.browser.services.browser_actions import BrowserActions
from nova_act.cli.browser.services.browser_config import DefaultBrowserConfig
from nova_act.cli.browser.utils.decorators import (
    browser_command_options,
    pack_command_params,
)
from nova_act.cli.browser.utils.error_handlers import handle_common_errors
from nova_act.cli.browser.utils.session import command_session, prepare_session
from nova_act.cli.browser.utils.validation_utils import (
    validate_prompt,
    validate_starting_page,
)
from nova_act.cli.core.json_output import ErrorCode
from nova_act.cli.core.output import echo_success, exit_with_error

if TYPE_CHECKING:
    from nova_act.cli.browser.types import CommandParams


@click.command("scroll-to")
@click.argument("target")
@click.option("--max-attempts", type=int, default=5, show_default=True, help="Max scroll+verify attempts")
@click.option(
    "--timeout",
    type=int,
    default=DefaultBrowserConfig.DEFAULT_ACT_TIMEOUT_SECONDS,
    show_default=True,
    help="Timeout in seconds for each act/act_get call",
)
@click.option("--starting-page", help="Starting URL for new sessions (default: about:blank)")
@browser_command_options
@handle_common_errors
@pack_command_params
def scroll_to(
    target: str,
    max_attempts: int,
    timeout: int,
    starting_page: str | None,
    params: CommandParams,
) -> None:
    """Scroll to a target section or content on the current page.

    Iteratively scrolls and verifies whether the target content is visible.
    Does NOT navigate to other pages — scrolling only.

    \b
    ⚠ Cost: Each attempt = 2 inference calls (scroll + verify). Default 5 attempts = up to 10 calls.

    Examples:
        act browser scroll-to "the pricing section" --session-id my-session
        act browser scroll-to "the footer" --max-attempts 3
        act browser scroll-to "the FAQ section" --starting-page https://example.com --json
    """
    validate_prompt(target)
    validate_starting_page(starting_page)

    prep = prepare_session(params, starting_page)

    with command_session("scroll_to", prep.manager, prep.session_info, params, log_args={"target": target}) as nova_act:
        actions = BrowserActions(nova_act)
        result = actions.scroll_to(target, max_attempts=max_attempts, timeout=timeout, **prep.method_args)

    details: dict[str, object] = {k: v for k, v in asdict(result).items() if k != "target"}
    if result.attempts == 0:
        details.pop("attempts", None)

    if result.reached:
        echo_success("Scroll target reached", details=details)
    else:
        exit_with_error(
            "Scroll target not found",
            f"Could not find '{target}' after {result.attempts} attempt(s)",
            suggestions=["Try increasing --max-attempts", "Try a more specific target description"],
            error_code=ErrorCode.NAVIGATION_ERROR,
            retryable=True,
        )
