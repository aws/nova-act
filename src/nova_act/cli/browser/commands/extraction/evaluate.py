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
"""Evaluate command for browser CLI."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import click
from playwright.sync_api import Error as PlaywrightError

from nova_act.cli.browser.services.browser_actions import (
    DEFAULT_EVALUATE_TIMEOUT_SECONDS,
    BrowserActions,
    is_complex_result,
)
from nova_act.cli.browser.utils.decorators import (
    browser_command_options,
    pack_command_params,
)
from nova_act.cli.browser.utils.error_handlers import handle_common_errors
from nova_act.cli.browser.utils.file_output import (
    OutputPathConfig,
    generate_output_path,
    validate_output_dir,
    write_output_file,
)
from nova_act.cli.browser.utils.session import command_session, prepare_session
from nova_act.cli.core.cli_stdout import get_cli_stdout
from nova_act.cli.core.json_output import ErrorCode, is_json_mode
from nova_act.cli.core.output import echo_success, exit_with_error

if TYPE_CHECKING:
    from nova_act.cli.browser.types import CommandParams

EVALUATE_OUTPUT = OutputPathConfig("eval", "json")


@click.command(name="evaluate")
@click.argument("expression")
@click.option("--output", "-o", help="Output file path (auto-generated for complex results if not specified)")
@click.option(
    "--timeout",
    type=int,
    default=DEFAULT_EVALUATE_TIMEOUT_SECONDS,
    show_default=True,
    help="Evaluation timeout in seconds",
)
@click.option("--starting-page", help="Starting URL for new sessions (default: about:blank)")
@browser_command_options
@handle_common_errors
@pack_command_params
def evaluate(
    expression: str,
    output: str | None,
    timeout: int,
    starting_page: str | None,
    params: CommandParams,
) -> None:
    """Evaluate a JavaScript expression in the current page context.

    \b
    ⚠️  SECURITY WARNING: This executes arbitrary JavaScript in the page context.
    Only use expressions you trust. Malicious JS can access cookies, session
    tokens, and page data.

    Examples:
        act browser evaluate "document.title"
        act browser evaluate "1 + 1"
        act browser evaluate "document.querySelectorAll('a').length" --json
        act browser evaluate "window.location.href" --session-id my-session
        act browser evaluate "[...document.querySelectorAll('a')].map(a => a.href)" --output links.json
        act browser evaluate "longRunningFunction()" --timeout 60
    """
    if output:
        validate_output_dir(output)

    prep = prepare_session(params, starting_page)

    with command_session(
        "evaluate",
        prep.manager,
        prep.session_info,
        params,
        log_args={"expression": expression, "output": output, "timeout": timeout},
    ) as nova_act:
        actions = BrowserActions(nova_act)
        try:
            result: object = actions.evaluate_js(expression, timeout=timeout)
        except PlaywrightError as e:
            if "Evaluation timed out" in str(e):
                exit_with_error(
                    "Evaluation timed out",
                    f"JavaScript expression did not complete within {timeout}s.",
                    suggestions=[
                        "Increase --timeout for long-running expressions",
                        "Simplify the expression",
                    ],
                    error_code=ErrorCode.BROWSER_ERROR,
                )
            raise

        file_path = _resolve_file_path(output, result)
        if file_path:
            _write_result_to_file(file_path, result)

        details = _build_details(params.session_id, expression, file_path, result)
        echo_success("Expression evaluated", details=details)

        if not is_json_mode() and not file_path:
            click.echo(f"\n--- Result ---\n{result}", file=get_cli_stdout())


def _resolve_file_path(output: str | None, result: object) -> str | None:
    """Determine output file path: user-provided, auto-generated for complex results, or None."""
    if output:
        return output
    if is_complex_result(result):
        return generate_output_path(EVALUATE_OUTPUT.filename, EVALUATE_OUTPUT.ext)
    return None


def _write_result_to_file(file_path: str, result: object) -> None:
    """Write evaluation result to file, formatting complex results as JSON."""
    content = json.dumps(result, indent=2) if is_complex_result(result) else str(result)
    write_output_file(file_path, content)


def _build_details(session_id: str, expression: str, file_path: str | None, result: object) -> dict[str, object]:
    """Build details dict for echo_success output."""
    details: dict[str, object] = {}
    if file_path:
        details["file"] = file_path
    else:
        details["result"] = result if is_json_mode() else repr(result)
    return details
