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
"""Tab-new command — open a new browser tab."""

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
from nova_act.cli.core.output import echo_success

if TYPE_CHECKING:
    from nova_act.cli.browser.types import CommandParams


@click.command("tab-new")
@click.option("--url", default="about:blank", help="URL to open in the new tab (default: about:blank)")
@browser_command_options
@handle_common_errors
@pack_command_params
def tab_new(url: str, params: CommandParams) -> None:
    """Open a new browser tab, optionally navigating to a URL.

    Creates a new tab in the current browser context and makes it active.

    Examples:
        act browser tab-new
        act browser tab-new --url https://example.com
        act browser tab-new --session-id my-session --json
    """
    prep = prepare_session(params, None)

    with command_session("tab-new", prep.manager, prep.session_info, params, log_args={"url": url}) as nova_act:
        context = get_active_page(nova_act, prep.session_info).context
        new_page = context.new_page()
        if url != "about:blank":
            new_page.goto(url)
        new_page.bring_to_front()
        pages = context.pages
        index = list(pages).index(new_page)
        tab_url = new_page.url
        tab_title = new_page.title()

        # Update active tab to the newly created tab
        prep.session_info.active_tab_index = index
        prep.manager.save_session_metadata(prep.session_info)

    echo_success(
        "New tab opened",
        details={"index": index, "url": tab_url, "title": tab_title},
    )
