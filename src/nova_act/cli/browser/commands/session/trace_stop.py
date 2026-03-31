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
"""Trace-stop command — stop Playwright tracing and save trace file."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import click

from nova_act.cli.browser.utils.decorators import (
    browser_command_options,
    pack_command_params,
)
from nova_act.cli.browser.utils.error_handlers import handle_common_errors
from nova_act.cli.browser.utils.log_capture import get_log_dir
from nova_act.cli.browser.utils.session import (
    command_session,
    get_active_page,
    prepare_session,
)
from nova_act.cli.core.output import echo_success

if TYPE_CHECKING:
    from nova_act.cli.browser.types import CommandParams


@click.command(name="trace-stop")
@click.option("--output", "output_path", type=click.Path(), default=None, help="Output path for trace .zip file")
@browser_command_options
@handle_common_errors
@pack_command_params
def trace_stop(output_path: str | None, params: CommandParams) -> None:
    """Stop Playwright tracing and save the trace file.

    Saves a .zip trace file viewable with 'npx playwright show-trace <file>'.

    Examples:
        act browser session trace-stop
        act browser session trace-stop --output ./my-trace.zip
    """
    prep = prepare_session(params, None)

    if output_path is None:
        log_dir = get_log_dir(params.session_id)
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(log_dir / f"trace_{timestamp}.zip")

    with command_session(
        "trace-stop",
        prep.manager,
        prep.session_info,
        params,
        log_args={"output": output_path},
    ) as nova_act:
        get_active_page(nova_act, prep.session_info).context.tracing.stop(path=output_path)

    echo_success("Tracing stopped", details={"Trace file": output_path})
