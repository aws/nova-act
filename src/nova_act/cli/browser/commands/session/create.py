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
"""Session create command."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from nova_act.cli.browser.utils.auth import resolve_auth_mode
from nova_act.cli.browser.utils.decorators import (
    auth_options,
    common_browser_options,
    common_session_options,
    json_option,
    pack_command_params,
    quiet_option,
    verbose_option,
)
from nova_act.cli.browser.utils.error_handlers import handle_common_errors
from nova_act.cli.browser.utils.session import (
    build_browser_options_from_params,
    get_or_create_session,
    get_session_manager,
)
from nova_act.cli.browser.utils.validation_utils import (
    validate_session_available,
    warn_missing_protocol,
)
from nova_act.cli.core.output import echo_success

if TYPE_CHECKING:
    from nova_act.cli.browser.types import CommandParams


@click.command()
@click.argument("url")
@common_browser_options
@common_session_options
@auth_options
@click.option("--max-sessions", type=int, default=None, help="Maximum active sessions allowed (default: 5)")
@json_option
@quiet_option
@verbose_option
@handle_common_errors
@pack_command_params
def create(
    url: str,
    max_sessions: int | None,
    params: CommandParams,
) -> None:
    """Create a new browser session starting at a specific URL.

    Examples:
        act browser session create https://example.com
        act browser session create https://amazon.com --session-id my-session
        act browser session create https://example.com --nova-arg headless=false
        act browser session create https://example.com --headed
        act browser session create https://example.com --headless
        act browser session create https://example.com --max-sessions 10
    """
    warn_missing_protocol(url)
    manager = get_session_manager()
    validate_session_available(params.session_id, manager)

    auth_config = resolve_auth_mode(params.auth_mode, params.profile, params.region, params.workflow_name)
    browser_options = build_browser_options_from_params(
        params,
        auth_config=auth_config,
    )
    session_info = get_or_create_session(manager, params.session_id, url, browser_options, max_sessions=max_sessions)

    echo_success(
        f"Created session '{params.session_id}'",
        details={"State": session_info.state.value},
    )
