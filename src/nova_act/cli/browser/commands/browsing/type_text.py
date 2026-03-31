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
"""Type command — type text into a target element or focused element."""

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


@click.command("type")
@click.argument("text")
@click.option(
    "--target",
    default=None,
    help="Element to type into (natural language, CSS selector, or ref). If omitted, types into focused element.",
)
@click.option("--append", is_flag=True, default=False, help="Append to existing content instead of replacing")
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
def type_text(
    text: str,
    target: str | None,
    append: bool,
    timeout: int,
    starting_page: str | None,
    params: CommandParams,
) -> None:
    """Type text into a target element or the currently focused element.

    If --target is omitted, types into the currently focused input field.

    Examples:
        act browser type "hello world" --target "search box"
        act browser type "hello world"
        act browser type "hello world" --target "#search-input"
        act browser type "additional text" --target "search box" --append
    """
    validate_starting_page(starting_page)
    prep = prepare_session(params, starting_page)

    with command_session(
        "type", prep.manager, prep.session_info, params, log_args={"text": text, "target": target, "append": append}
    ) as nova_act:
        actions = BrowserActions(nova_act)
        result = actions.type_text(text, target=target, append=append, timeout=timeout, **prep.method_args)

        echo_success("Text typed", details={k: v for k, v in asdict(result).items() if k not in ("typed", "target")})
