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
"""Click command — click a target element on the current page."""

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
from nova_act.cli.browser.utils.validation_utils import validate_starting_page
from nova_act.cli.core.output import echo_success

if TYPE_CHECKING:
    from nova_act.cli.browser.types import CommandParams


@click.command("click")
@click.argument("target")
@click.option("--focus", help="Narrow AI attention to a specific page area")
@click.option(
    "--timeout",
    type=int,
    default=DefaultBrowserConfig.DEFAULT_ACT_TIMEOUT_SECONDS,
    show_default=True,
    help="Timeout in seconds",
)
@click.option("--starting-page", help="Starting URL for new sessions (default: about:blank)")
@browser_command_options
@handle_common_errors
@pack_command_params
def click_target(
    target: str,
    focus: str | None,
    timeout: int,
    starting_page: str | None,
    params: CommandParams,
) -> None:
    """Click a target element on the current page.

    TARGET can be a natural language description, CSS selector, or snapshot ref (e.g. e12).

    Examples:
        act browser click "Submit button"
        act browser click "#submit-btn"
        act browser click "e12"
        act browser click "Login" --focus "the navigation bar"
        act browser click "Add to cart" --starting-page https://example.com/shop
    """
    validate_starting_page(starting_page)
    prep = prepare_session(params, starting_page)

    with command_session(
        "click", prep.manager, prep.session_info, params, log_args={"target": target, "focus": focus}
    ) as nova_act:
        actions = BrowserActions(nova_act)
        result = actions.click(target, focus=focus, timeout=timeout, **prep.method_args)

        echo_success("Clicked target", details=asdict(result))
