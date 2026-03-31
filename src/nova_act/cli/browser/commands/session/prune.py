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
"""Session prune command."""

import click

from nova_act.cli.browser.utils.decorators import json_option
from nova_act.cli.browser.utils.error_handlers import handle_common_errors
from nova_act.cli.browser.utils.session import get_session_manager
from nova_act.cli.core.json_output import is_json_mode
from nova_act.cli.core.output import echo_success


@click.command()
@click.option("--ignore-ttl", is_flag=True, help="Prune all non-active sessions regardless of TTL")
@click.option("--dry-run", is_flag=True, help="Preview what would be pruned without deleting")
@json_option
@handle_common_errors
def prune(ignore_ttl: bool, dry_run: bool) -> None:
    """Remove stale sessions and their Chrome profile directories.

    By default, prunes sessions inactive for 24+ hours or with dead browser PIDs.
    Use --ignore-ttl to prune all non-active (stopped/failed) sessions regardless of TTL.

    Examples:
        act browser session prune
        act browser session prune --ignore-ttl
        act browser session prune --dry-run
    """
    manager = get_session_manager()
    results = manager.prune_sessions(ignore_ttl=ignore_ttl, dry_run=dry_run)

    if not results:
        if is_json_mode():
            echo_success("No sessions to prune", details={"sessions_pruned": [], "count": 0})
        else:
            echo_success("No sessions to prune", details={"Info": "All sessions are active or within TTL"})
        return

    action = "Would prune" if dry_run else "Pruned"
    if is_json_mode():
        pruned = [{"session_id": r.session_id, "profile_dir": r.user_data_dir} for r in results]
        echo_success(f"{action} {len(results)} session(s)", details={"sessions_pruned": pruned, "count": len(results)})
    else:
        details = {f"Session '{r.session_id}'": r.user_data_dir or "(no profile dir)" for r in results}
        echo_success(f"{action} {len(results)} session(s)", details=details)
