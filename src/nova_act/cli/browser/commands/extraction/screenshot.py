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
"""Screenshot command for browser CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from nova_act.cli.browser.services.browser_actions import BrowserActions
from nova_act.cli.browser.utils.browser_config_cli import DEFAULT_SCREENSHOT_QUALITY
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

SCREENSHOT_OUTPUT = OutputPathConfig("screenshot", "png")


@click.command()
@click.option("--output", "-o", help="Output file path for screenshot")
@click.option("--full-page", is_flag=True, default=False, help="Capture full page (default: viewport only)")
@click.option("--viewport-only", is_flag=True, default=False, help="Capture viewport only (inverse of --full-page)")
@click.option(
    "--format", "output_format", type=click.Choice(["png", "jpeg"]), default="png", help="Image format (default: png)"
)
@click.option(
    "--quality",
    type=click.IntRange(0, 100),
    default=DEFAULT_SCREENSHOT_QUALITY,
    help=f"JPEG quality 0-100 (default: {DEFAULT_SCREENSHOT_QUALITY})",
)
@click.option(
    "--annotate", is_flag=True, default=False, help="Overlay bounding boxes and ref labels on interactive elements"
)
@click.option(
    "--annotate-filter",
    default=None,
    help="Comma-separated roles to annotate (e.g. button,link). Default: all interactive roles",
)
@browser_command_options
@handle_common_errors
@pack_command_params
def screenshot(
    output: str | None,
    full_page: bool,
    viewport_only: bool,
    output_format: str,
    quality: int,
    annotate: bool,
    annotate_filter: str | None,
    params: CommandParams,
) -> None:
    """Capture a screenshot of the current page.

    Examples:
        act browser screenshot
        act browser screenshot --output screenshot.png
        act browser screenshot --annotate
        act browser screenshot --annotate --annotate-filter button,link
        act browser screenshot --full-page --output fullpage.png
    """
    prep = prepare_session(params, None)

    with command_session(
        "screenshot",
        prep.manager,
        prep.session_info,
        params,
        log_args={"output": output, "format": output_format, "annotate": annotate},
    ) as nova_act:
        output = resolve_output_path(output, SCREENSHOT_OUTPUT.filename, output_format)
        effective_full_page = False if viewport_only else full_page
        actions = BrowserActions(nova_act)
        screenshot_bytes = actions.screenshot(
            full_page=effective_full_page, output_format=output_format, quality=quality
        )

        annotation_count = 0
        if annotate:
            from nova_act.cli.browser.services.screenshot_annotator import (
                annotate_page_screenshot,
            )

            active_page = get_active_page(nova_act, prep.session_info)
            screenshot_bytes, annotation_count = annotate_page_screenshot(
                active_page, screenshot_bytes, annotate_filter
            )

        write_output_file(output, screenshot_bytes)

        details: dict[str, str] = {
            "file": output,
            "size": str(len(screenshot_bytes)),
            "format": output_format.upper(),
            "full_page": "Yes" if effective_full_page else "No",
        }
        if output_format == "jpeg":
            details["quality"] = str(quality)
        if annotate:
            details["annotations"] = f"{annotation_count} elements labeled"
        echo_success(f"Screenshot saved to {output}", details=details)
