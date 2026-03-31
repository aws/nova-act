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
"""Wait-for command — poll until a condition is met on the current page."""

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
from nova_act.cli.core.json_output import ErrorCode
from nova_act.cli.core.output import echo_success, exit_with_error

if TYPE_CHECKING:
    from nova_act.cli.browser.types import CommandParams


@click.command("wait-for")
@click.argument("condition")
@click.option("--timeout", type=int, default=30, show_default=True, help="Maximum seconds to wait for the condition")
@click.option(
    "--interval", type=int, default=5, show_default=True, help="Seconds between polls. Each poll = 1 inference call"
)
@click.option("--focus", help="Focus polling on a specific page area")
@click.option("--starting-page", help="Starting URL for new sessions (default: about:blank)")
@browser_command_options
@handle_common_errors
@pack_command_params
def wait_for(
    condition: str,
    timeout: int,
    interval: int,
    focus: str | None,
    starting_page: str | None,
    params: CommandParams,
) -> None:
    """Poll until a condition is met on the current page.

    Each poll is one inference call that checks whether CONDITION is true.

    \b
    ⚠ Cost: Each poll = 1 inference call. A 30s timeout with 5s interval = up to 6 calls.

    Examples:
        act browser wait-for "the loading spinner is gone" --session-id my-session
        act browser wait-for "results are visible" --timeout 60 --interval 10
        act browser wait-for "the modal is open" --focus "the dialog area" --json
    """
    validate_starting_page(starting_page)

    prep = prepare_session(params, starting_page)

    try:
        with command_session(
            "wait_for",
            prep.manager,
            prep.session_info,
            params,
            log_args={"condition": condition, "timeout": timeout, "interval": interval},
        ) as nova_act:
            actions = BrowserActions(nova_act)
            result = actions.wait_for(
                condition,
                timeout=timeout,
                interval=interval,
                focus=focus,
                per_call_timeout=DefaultBrowserConfig.DEFAULT_ACT_TIMEOUT_SECONDS,
                **prep.method_args,
            )
    except RuntimeError as e:
        exit_with_error(
            "Condition not met",
            str(e),
            suggestions=[
                "Increase --timeout for slower pages",
                "Adjust --interval to poll more or less frequently",
                "Verify the condition text matches what appears on the page",
            ],
            error_code=ErrorCode.TIMEOUT_ERROR,
            retryable=True,
        )

    if result.met:
        echo_success(
            "Condition met",
            details=asdict(result),
        )
    else:
        exit_with_error(
            "Condition not met",
            f"Condition '{condition}' was not met after {result.polls} poll(s) within {timeout}s timeout",
            suggestions=[
                "Increase --timeout for slower pages",
                "Adjust --interval to poll more or less frequently",
                "Verify the condition text matches what appears on the page",
            ],
            error_code=ErrorCode.TIMEOUT_ERROR,
            retryable=True,
        )
