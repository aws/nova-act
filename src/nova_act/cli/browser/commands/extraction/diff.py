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
"""Diff command — observe page state before and after an action."""

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


@click.command()
@click.argument("action")
@click.option("--observe-prompt", help="Custom observation prompt (overrides default)")
@click.option("--schema", help="JSON Schema for observation response (overrides default)")
@click.option("--focus", help="Focus observations on a specific page area")
@click.option(
    "--timeout",
    type=int,
    default=DefaultBrowserConfig.DEFAULT_ACT_TIMEOUT_SECONDS,
    show_default=True,
    help="Timeout in seconds for each inference call",
)
@click.option("--starting-page", help="Starting URL for new sessions (default: about:blank)")
@browser_command_options
@handle_common_errors
@pack_command_params
def diff(
    action: str,
    observe_prompt: str | None,
    schema: str | None,
    focus: str | None,
    timeout: int,
    starting_page: str | None,
    params: CommandParams,
) -> None:
    """Observe page state before and after an action.

    Takes three inference calls: observe before, execute ACTION, observe after.

    Examples:
        act browser diff "Click the submit button" --session-id my-session
        act browser diff "Toggle dark mode" --observe-prompt "What is the background color?" --json
        act browser diff "Add item to cart" --focus "the cart icon" --starting-page https://example.com
    """
    validate_starting_page(starting_page)

    prep = prepare_session(params, starting_page)

    with command_session(
        "diff",
        prep.manager,
        prep.session_info,
        params,
        log_args={"action": action, "observe_prompt": observe_prompt, "focus": focus},
    ) as nova_act:
        actions = BrowserActions(nova_act)
        result = actions.diff(
            action, observe=observe_prompt, schema=schema, focus=focus, timeout=timeout, **prep.method_args
        )

        echo_success(
            "Diff complete",
            details={k: v for k, v in asdict(result).items() if k != "action"},
        )
