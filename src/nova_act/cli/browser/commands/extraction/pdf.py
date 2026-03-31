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
"""PDF export command for browser CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from nova_act.cli.browser.utils.decorators import (
    browser_command_options,
    pack_command_params,
)
from nova_act.cli.browser.utils.error_handlers import handle_common_errors
from nova_act.cli.browser.utils.file_output import (
    OutputPathConfig,
    resolve_output_path,
    write_output_file,
)
from nova_act.cli.browser.utils.session import (
    command_session,
    get_active_page,
    prepare_session,
)
from nova_act.cli.core.output import echo_success

if TYPE_CHECKING:
    from nova_act.cli.browser.types import CommandParams

PDF_OUTPUT = OutputPathConfig("page", "pdf")


@click.command()
@click.option("--output", "-o", help="Output file path for PDF")
@click.option(
    "--format",
    "paper_format",
    type=click.Choice(["letter", "a4", "a3", "legal", "tabloid"]),
    default="letter",
    help="Paper format (default: letter)",
)
@click.option("--landscape", is_flag=True, default=False, help="Landscape orientation")
@click.option("--print-background", is_flag=True, default=False, help="Include background graphics")
@click.option(
    "--scale",
    type=click.FloatRange(0.1, 2.0),
    default=1.0,
    help="Scale factor 0.1-2.0 (default: 1.0)",
)
@click.option("--page-ranges", default=None, help="Page ranges to print (e.g. '1-3, 5')")
@browser_command_options
@handle_common_errors
@pack_command_params
def pdf(
    output: str | None,
    paper_format: str,
    landscape: bool,
    print_background: bool,
    scale: float,
    page_ranges: str | None,
    params: CommandParams,
) -> None:
    """Export the current page as a PDF.

    Note: PDF export requires headless mode. Use --headless on session create.

    Examples:
        act browser pdf
        act browser pdf --output report.pdf
        act browser pdf --format a4 --landscape
        act browser pdf --print-background --scale 0.8
    """
    prep = prepare_session(params, None)

    with command_session(
        "pdf",
        prep.manager,
        prep.session_info,
        params,
        log_args={"output": output, "format": paper_format},
    ) as nova_act:
        output = resolve_output_path(output, PDF_OUTPUT.filename, "pdf")
        # Playwright expects: Letter, Legal, Tabloid, A3, A4
        format_map = {"letter": "Letter", "legal": "Legal", "tabloid": "Tabloid", "a3": "A3", "a4": "A4"}
        pdf_kwargs: dict[str, object] = {
            "format": format_map[paper_format],
            "landscape": landscape,
            "print_background": print_background,
            "scale": scale,
        }
        if page_ranges:
            pdf_kwargs["page_ranges"] = page_ranges

        pdf_bytes = get_active_page(nova_act, prep.session_info).pdf(**pdf_kwargs)  # type: ignore[arg-type]

        write_output_file(output, pdf_bytes)

        details: dict[str, str] = {
            "File": output,
            "Size": f"{len(pdf_bytes)} bytes",
            "Landscape": "Yes" if landscape else "No",
            "Scale": str(scale),
        }
        if print_background:
            details["Background"] = "Yes"
        if page_ranges:
            details["Pages"] = page_ranges
        echo_success(f"PDF saved to {output}", details=details)
