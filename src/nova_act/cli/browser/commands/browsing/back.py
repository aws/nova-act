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
"""Back command — navigate browser history backward."""

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


@click.command()
@browser_command_options
@handle_common_errors
@pack_command_params
def back(params: CommandParams) -> None:
    """Go back one page in browser history (Playwright go_back).

    Examples:
        act browser back
        act browser back --session-id my-session
    """
    prep = prepare_session(params, None)

    with command_session("back", prep.manager, prep.session_info, params, log_args={}) as nova_act:
        page = get_active_page(nova_act, prep.session_info)
        page.go_back(wait_until="commit")
        url = page.url
        title = page.title()

    echo_success("Navigated back", details={"URL": url, "Title": title})
