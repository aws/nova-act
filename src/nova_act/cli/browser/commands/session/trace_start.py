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
"""Trace-start command — begin Playwright tracing."""

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


@click.command(name="trace-start")
@click.option("--screenshots/--no-screenshots", default=True, help="Capture screenshots in trace (default: true)")
@click.option("--snapshots/--no-snapshots", default=True, help="Capture DOM snapshots in trace (default: true)")
@browser_command_options
@handle_common_errors
@pack_command_params
def trace_start(screenshots: bool, snapshots: bool, params: CommandParams) -> None:
    """Start Playwright tracing for the current session.

    Captures a detailed trace including screenshots, DOM snapshots, and network
    activity. Stop with 'trace-stop' to save the trace file.

    Examples:
        act browser session trace-start
        act browser session trace-start --no-screenshots
    """
    prep = prepare_session(params, None)

    with command_session(
        "trace-start",
        prep.manager,
        prep.session_info,
        params,
        log_args={"screenshots": screenshots, "snapshots": snapshots},
    ) as nova_act:
        get_active_page(nova_act, prep.session_info).context.tracing.start(screenshots=screenshots, snapshots=snapshots)

    echo_success("Tracing started", details={"Screenshots": str(screenshots), "Snapshots": str(snapshots)})
