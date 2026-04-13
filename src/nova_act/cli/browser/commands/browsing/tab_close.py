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

from nova_act.cli.browser.services.browser_actions import BrowserActions
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
        active_page = get_active_page(nova_act, prep.session_info)
        context = active_page.context
        actions = BrowserActions(nova_act)

        try:
            result = actions.close_tab(context, tab_id, active_page)
        except ValueError:
            exit_with_error(
                "Cannot close last tab",
                "At least one tab must remain open",
                suggestions=["Use 'session stop' to end the browser session instead"],
                error_code=ErrorCode.VALIDATION_ERROR,
            )
        except IndexError as exc:
            exit_with_error(
                "Invalid tab index",
                str(exc),
                suggestions=["Use 'tab-list' to see available tabs"],
                error_code=ErrorCode.VALIDATION_ERROR,
            )

        prep.session_info.active_tab_index = result["new_active_index"]  # type: ignore[assignment]
        prep.manager.save_session_metadata(prep.session_info)

    echo_success("Tab closed", details=result)
