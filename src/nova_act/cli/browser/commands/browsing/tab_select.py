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
"""Tab-select command — switch to a browser tab by index."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from nova_act.cli.browser.utils.decorators import (
    browser_command_options,
    pack_command_params,
)
from nova_act.cli.browser.utils.error_handlers import handle_common_errors
from nova_act.cli.browser.utils.session import command_session, prepare_session
from nova_act.cli.core.json_output import ErrorCode
from nova_act.cli.core.output import echo_success, exit_with_error

if TYPE_CHECKING:
    from nova_act.cli.browser.types import CommandParams


@click.command("tab-select")
@click.argument("index", type=int)
@browser_command_options
@handle_common_errors
@pack_command_params
def tab_select(index: int, params: CommandParams) -> None:
    """Switch to a browser tab by its index.

    Use 'tab-list' to see available tab indices.

    Examples:
        act browser tab-select 0
        act browser tab-select 2 --session-id my-session
        act browser tab-select 1 --json
    """
    prep = prepare_session(params, None)

    with command_session("tab-select", prep.manager, prep.session_info, params, log_args={"index": index}) as nova_act:
        pages = nova_act.page.context.pages
        if index < 0 or index >= len(pages):
            exit_with_error(
                "Invalid tab index",
                f"Index {index} out of range (0-{len(pages) - 1})",
                suggestions=["Use 'tab-list' to see available tabs"],
                error_code=ErrorCode.VALIDATION_ERROR,
            )
        selected = pages[index]
        selected.bring_to_front()
        url = selected.url
        title = selected.title()

        # Persist active tab index so subsequent commands operate on this tab
        prep.session_info.active_tab_index = index
        prep.manager.save_session_metadata(prep.session_info)

    echo_success(
        "Tab selected",
        details={"index": index, "url": url, "title": title},
    )
