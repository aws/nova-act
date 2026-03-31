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
"""Execute command — primary delegation interface for multi-step browser plans."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from nova_act.cli.browser.types import CommandParams

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
from nova_act.cli.core.output import echo_success


@click.command()
@click.argument("prompt")
@click.option(
    "--timeout",
    type=int,
    default=DefaultBrowserConfig.DEFAULT_ACT_TIMEOUT_SECONDS,
    show_default=True,
    help="Timeout in seconds for the act() call",
)
@click.option("--starting-page", help="Starting URL for new sessions (default: about:blank)")
@browser_command_options
@handle_common_errors
@pack_command_params
def execute(
    prompt: str,
    timeout: int,
    starting_page: str | None,
    params: CommandParams,
) -> None:
    """Delegate a multi-step browser plan to the visual intelligence agent.

    This is the primary delegation command. Pass a full natural language plan
    describing everything the agent should do in the browser — multiple steps,
    navigation, interactions, and assertions can all be included in a single call.
    The agent executes the entire plan sequentially.

    Default to execute with a detailed multi-step plan. Only drop to individual
    commands (click, goto, snapshot) for error recovery or surgical precision.

    Examples:
        act browser execute "Go to amazon.com, search for laptops, click the first result, and extract the price"
        act browser execute "Navigate to github.com/login, enter username and password, click Sign in"
        act browser execute "Open the settings page, enable dark mode, and confirm the theme changed"
        act browser execute "Search for 'wireless headphones' on bestbuy.com and add the top-rated result to the cart"
        act browser execute "Fill out the contact form with name and email, then submit it" --session-id my-session
        act browser execute "Click the first result" --headed
        act browser execute "test action" --nova-arg max_steps=5
    """
    validate_prompt(prompt)
    validate_starting_page(starting_page)

    prep = prepare_session(params, starting_page)

    with command_session(
        "execute", prep.manager, prep.session_info, params, log_args={"prompt": prompt, "timeout": timeout}
    ) as nova_act:
        actions = BrowserActions(nova_act)
        result = actions.execute(prompt, timeout=timeout, **prep.method_args)

    echo_success(
        "Action completed",
        details=asdict(result),
    )
