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
"""Verify command — assert a condition on the current page with CI-friendly exit codes."""

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


@click.command()
@click.argument("assertion")
@click.option("--focus", help="Focus verification on a specific page area")
@click.option(
    "--timeout",
    type=int,
    default=DefaultBrowserConfig.DEFAULT_ACT_TIMEOUT_SECONDS,
    show_default=True,
    help="Timeout in seconds for the verification call",
)
@click.option("--starting-page", help="Starting URL for new sessions (default: about:blank)")
@browser_command_options
@handle_common_errors
@pack_command_params
def verify(
    assertion: str,
    focus: str | None,
    timeout: int,
    starting_page: str | None,
    params: CommandParams,
) -> None:
    """Assert a condition on the current page. Exit code 0 on pass, 1 on fail.

    Uses AI to determine if ASSERTION is true on the page. Returns structured
    pass/fail with evidence — ideal for CI/CD pipelines and test scripts.

    Examples:
        act browser verify "the login button is visible" --session-id my-session
        act browser verify "the price is $29.99" --focus "the pricing section"
        act browser verify "there are exactly 5 items in the cart" --json
    """
    validate_starting_page(starting_page)

    prep = prepare_session(params, starting_page)

    with command_session(
        "verify", prep.manager, prep.session_info, params, log_args={"assertion": assertion, "focus": focus}
    ) as nova_act:
        actions = BrowserActions(nova_act)
        result = actions.verify(assertion, focus=focus, timeout=timeout, **prep.method_args)

    if result.passed:
        echo_success("Assertion passed", details=asdict(result))
    else:
        exit_with_error(
            "Assertion failed",
            f"Assertion failed: {assertion}",
            suggestions=[
                "Check that the assertion text matches what appears on the page",
                "Use --focus to narrow verification to a specific area",
                "Use --json for structured output in CI pipelines",
            ],
            error_code=ErrorCode.ASSERTION_FAILED,
            retryable=False,
            details=asdict(result),
        )
