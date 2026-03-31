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
"""Ask command — read-only question about the current page."""

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
@click.argument("question")
@click.option("--schema", help="JSON Schema (Draft 7) for structured answer (overrides default)")
@click.option("--focus", help="Focus answer on a specific page area")
@click.option(
    "--timeout",
    type=int,
    default=DefaultBrowserConfig.DEFAULT_ACT_TIMEOUT_SECONDS,
    show_default=True,
    help="Timeout in seconds for the act_get() call",
)
@click.option("--starting-page", help="Starting URL for new sessions (default: about:blank)")
@browser_command_options
@handle_common_errors
@pack_command_params
def ask(
    question: str,
    schema: str | None,
    focus: str | None,
    timeout: int,
    starting_page: str | None,
    params: CommandParams,
) -> None:
    """Ask a read-only question about the current page.

    Does not interact with the page — observation only.

    Examples:
        act browser ask "What is the main heading?" --session-id my-session
        act browser ask "What is the price?" --focus "the checkout summary" --json
        act browser ask "What links are on this page?" --schema '{"type":"object","properties":{"links":{"type":"array","items":{"type":"string"}}}}'  # noqa: E501
        act browser ask "What is on this page?" --starting-page https://example.com
    """
    validate_starting_page(starting_page)

    prep = prepare_session(params, starting_page)

    with command_session(
        "ask", prep.manager, prep.session_info, params, log_args={"question": question, "focus": focus}
    ) as nova_act:
        actions = BrowserActions(nova_act)
        result = actions.ask(question, schema=schema, focus=focus, timeout=timeout, **prep.method_args)

    echo_success("Question answered", details={k: v for k, v in asdict(result).items() if k != "question"})
