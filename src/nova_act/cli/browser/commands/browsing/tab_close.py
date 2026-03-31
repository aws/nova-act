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
"""Tab-close command — close a browser tab."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from nova_act.cli.browser.utils.decorators import (
    browser_command_options,
    pack_command_params,
)
from nova_act.cli.browser.utils.error_handlers import handle_common_errors
from nova_act.cli.browser.utils.session import (
    command_session,
    get_active_page,
    prepare_session,
)
from nova_act.cli.core.json_output import ErrorCode
from nova_act.cli.core.output import echo_success, exit_with_error

if TYPE_CHECKING:
    from nova_act.cli.browser.types import CommandParams


@click.command("tab-close")
@click.option("--tab-id", type=int, default=None, help="Index of tab to close (default: active tab)")
@browser_command_options
@handle_common_errors
@pack_command_params
def tab_close(tab_id: int | None, params: CommandParams) -> None:
    """Close a browser tab by index, or the active tab if no index given.

    After closing, switches to the nearest remaining tab.
    Cannot close the last remaining tab.

    Examples:
        act browser tab-close
        act browser tab-close --tab-id 2
        act browser tab-close --session-id my-session --json
    """
    prep = prepare_session(params, None)

    with command_session("tab-close", prep.manager, prep.session_info, params, log_args={"tab_id": tab_id}) as nova_act:
        pages = nova_act.page.context.pages
        if len(pages) <= 1:
            exit_with_error(
                "Cannot close last tab",
                "At least one tab must remain open",
                suggestions=["Use 'session stop' to end the browser session instead"],
                error_code=ErrorCode.VALIDATION_ERROR,
            )

        if tab_id is None:
            target = get_active_page(nova_act, prep.session_info)
            tab_id = list(pages).index(target)
        else:
            if tab_id < 0 or tab_id >= len(pages):
                exit_with_error(
                    "Invalid tab index",
                    f"Index {tab_id} out of range (0-{len(pages) - 1})",
                    suggestions=["Use 'tab-list' to see available tabs"],
                    error_code=ErrorCode.VALIDATION_ERROR,
                )
            target = pages[tab_id]

        closed_url = target.url
        closed_title = target.title()
        target.close()

        # Switch to nearest remaining tab
        remaining = nova_act.page.context.pages
        new_index = min(tab_id, len(remaining) - 1)
        remaining[new_index].bring_to_front()

        # Persist new active tab index
        prep.session_info.active_tab_index = new_index
        prep.manager.save_session_metadata(prep.session_info)

    echo_success(
        "Tab closed",
        details={
            "closed_index": tab_id,
            "closed_url": closed_url,
            "closed_title": closed_title,
            "new_active_index": new_index,
        },
    )
