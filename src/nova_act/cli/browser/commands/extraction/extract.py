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
"""Extract command — delegate data extraction plans to the browser agent."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click

from nova_act.cli.browser.services.browser_actions import BrowserActions
from nova_act.cli.browser.services.browser_config import DefaultBrowserConfig
from nova_act.cli.browser.utils.decorators import (
    browser_command_options,
    pack_command_params,
)
from nova_act.cli.browser.utils.error_handlers import handle_common_errors
from nova_act.cli.browser.utils.file_output import (
    OutputPathConfig,
    format_result,
    resolve_output_path,
    write_output_file,
)
from nova_act.cli.browser.utils.session import command_session, prepare_session
from nova_act.cli.browser.utils.validation_utils import (
    require_argument,
    validate_starting_page,
)
from nova_act.cli.core.output import echo_success

if TYPE_CHECKING:
    from nova_act.cli.browser.types import CommandParams

EXTRACTION_OUTPUT = OutputPathConfig("extraction", "txt")


@click.command()
@click.argument("prompt", required=False)
@click.option("--schema", help="JSON schema for structured extraction (supports 'bool', 'string', or full JSON)")
@click.option(
    "--timeout",
    type=int,
    default=DefaultBrowserConfig.DEFAULT_ACT_TIMEOUT_SECONDS,
    show_default=True,
    help="Timeout in seconds for the act_get() call",
)
@click.option("--format", "output_format", type=click.Choice(["json", "text"]), default="text", help="Output format")
@click.option("--output", "-o", help="Output file path (auto-generated if not specified)")
@click.option("--starting-page", help="Starting URL for new sessions (default: about:blank)")
@browser_command_options
@handle_common_errors
@pack_command_params
def extract(
    prompt: str | None,
    schema: str | None,
    timeout: int,
    output_format: str,
    output: str | None,
    starting_page: str | None,
    params: CommandParams,
) -> None:
    """Extract structured data from the browser, potentially across multiple steps.

    Describe what data you need and how to find it as a natural language plan.
    The agent will navigate, interact, and extract — all from a single prompt.
    Use --schema to constrain the output to a specific type (bool, string, or JSON).

    Examples:
        act browser extract "Go to amazon.com, search for laptops, and get the top 5 results"
        act browser extract "Navigate to the pricing page and extract plan names" --schema string
        act browser extract "Open the user profile and get all field values" --session-id my-session
        act browser extract "Check if the checkout button is enabled" --schema bool
        act browser extract "Get all product prices on this page" --format json -o prices.json
        act browser extract "Get the article title and author" --starting-page https://example.com/blog
        act browser extract "Get title" --nova-arg max_steps=3
    """
    require_argument(prompt, "prompt", "act browser extract 'Get all product prices'")
    validate_starting_page(starting_page)
    assert prompt is not None

    prep = prepare_session(params, starting_page)

    ext = "json" if output_format == "json" else "txt"
    with command_session(
        "extract",
        prep.manager,
        prep.session_info,
        params,
        log_args={"prompt": prompt, "schema": schema, "output": output},
    ) as nova_act:
        output = resolve_output_path(output, EXTRACTION_OUTPUT.filename, ext)
        actions = BrowserActions(nova_act)
        extraction_data = actions.extract(prompt, schema=schema, timeout=timeout, **prep.method_args)

    formatted_result = format_result(extraction_data, output_format)
    file_size = write_output_file(output, formatted_result)

    details: dict[str, object] = {
        "file": output,
        "size": file_size,
    }
    if file_size < 4096:
        details["content"] = Path(output).read_text()
        details["content_truncated"] = False
    echo_success("Extraction complete", details=details)
