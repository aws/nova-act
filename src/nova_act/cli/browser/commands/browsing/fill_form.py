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
"""Fill-form command — fill out a form using JSON field data with per-field resolution."""

from __future__ import annotations

import json
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


@click.command("fill-form")
@click.argument("json_data")
@click.option("--submit", "submit_form", is_flag=True, default=False, help="Submit the form after filling")
@click.option("--focus", help="Focus on a specific form area")
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
def fill_form(
    json_data: str,
    submit_form: bool,
    focus: str | None,
    timeout: int,
    starting_page: str | None,
    params: CommandParams,
) -> None:
    """Fill out a form on the current page using JSON field data.

    JSON_DATA is a JSON object mapping field names/selectors to values.

    Avoid passing sensitive credentials via CLI arguments as they may appear in shell history.

    Examples:
        act browser fill-form '{"Full Name": "John Smith", "Email": "john@example.com"}'
        act browser fill-form '{"search_query": "example", "quantity": "1"}' --submit
        act browser fill-form '{"#search": "test query"}' --focus "the search form"
    """
    try:
        fields = json.loads(json_data)
    except json.JSONDecodeError as exc:
        raise click.BadParameter(f"Invalid JSON: {exc}") from exc

    if not isinstance(fields, dict):
        raise click.BadParameter("JSON_DATA must be a JSON object (dict), not a list or scalar.")

    validate_starting_page(starting_page)

    prep = prepare_session(params, starting_page)

    with command_session(
        "fill_form", prep.manager, prep.session_info, params, log_args={"json_data": json_data, "submit": submit_form}
    ) as nova_act:
        actions = BrowserActions(nova_act)
        result = actions.fill_form(fields, submit=submit_form, focus=focus, timeout=timeout, **prep.method_args)

    echo_success(
        "Form filled",
        details={k: v for k, v in asdict(result).items() if k != "instruction"},
    )
