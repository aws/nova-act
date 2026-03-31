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
"""Browser session management commands.

This package splits session commands by responsibility:
- list: list_sessions command + display helpers
- close: close + close_all commands + batch helpers
- create: create command + validation
- prune: prune command
- record_show: display session recording manifest
- trace_start / trace_stop: Playwright tracing

Note: Click commands are imported with ``_cmd`` suffixes to avoid shadowing
submodule names, which breaks ``unittest.mock.patch()`` on Python 3.10.
"""

import click

from nova_act.cli.browser.commands.session.close import close as close_cmd
from nova_act.cli.browser.commands.session.close import close_all as close_all_cmd
from nova_act.cli.browser.commands.session.create import create as create_cmd
from nova_act.cli.browser.commands.session.export import export as export_cmd
from nova_act.cli.browser.commands.session.list import (
    _format_session_details,
)
from nova_act.cli.browser.commands.session.list import list_sessions as list_sessions_cmd
from nova_act.cli.browser.commands.session.prune import prune as prune_cmd
from nova_act.cli.browser.commands.session.record_show import record_show as record_show_cmd
from nova_act.cli.browser.commands.session.trace_start import trace_start as trace_start_cmd
from nova_act.cli.browser.commands.session.trace_stop import trace_stop as trace_stop_cmd
from nova_act.cli.group import StyledGroup


@click.group(cls=StyledGroup)
def session() -> None:
    """Manage browser sessions."""
    pass


# Register session subcommands
session.add_command(list_sessions_cmd)
session.add_command(close_cmd)
session.add_command(close_all_cmd)
session.add_command(create_cmd)
session.add_command(export_cmd)
session.add_command(prune_cmd)
session.add_command(record_show_cmd)
session.add_command(trace_start_cmd)
session.add_command(trace_stop_cmd)

__all__ = [
    "session",
    "_format_session_details",
]
