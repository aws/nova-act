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
"""Main entry point for Nova Act CLI."""

try:
    import click  # noqa: F401
except ImportError:
    raise ImportError("To use the Nova Act CLI, install with the [cli] extra: " "pip install --upgrade nova-act[cli]")

try:
    import yaml  # noqa: F401
except ImportError:
    raise ImportError("To use the Nova Act CLI, install with the [cli] extra: " "pip install --upgrade nova-act[cli]")

import os

from nova_act.cli.__version__ import VERSION
from nova_act.cli.browser import browser
from nova_act.cli.core.styling import initialize_theme
from nova_act.cli.core.theme import ThemeName, set_active_theme
from nova_act.cli.group import StyledGroup
from nova_act.cli.workflow.commands.create import create
from nova_act.cli.workflow.commands.delete import delete
from nova_act.cli.workflow.commands.deploy import deploy
from nova_act.cli.workflow.commands.list import list
from nova_act.cli.workflow.commands.list_runs import list_runs
from nova_act.cli.workflow.commands.run import run
from nova_act.cli.workflow.commands.show import show
from nova_act.cli.workflow.commands.update import update


@click.group(cls=StyledGroup)
@click.option("--profile", help="AWS profile to use (from ~/.aws/credentials)")
@click.pass_context
def workflow(ctx: click.Context, profile: str | None) -> None:
    """Workflow management commands."""
    if profile:
        os.environ["AWS_PROFILE"] = profile


workflow.add_command(create)
workflow.add_command(update)
workflow.add_command(delete)
workflow.add_command(show)
workflow.add_command(deploy)
workflow.add_command(run)
workflow.add_command(list)
workflow.add_command(list_runs)


@click.group(cls=StyledGroup)
@click.version_option(version=VERSION)
@click.option("--no-color", is_flag=True, help="Disable colored output")
def main(no_color: bool) -> None:
    """Nova Act CLI."""
    initialize_theme()
    if no_color:
        set_active_theme(ThemeName.NONE)


main.add_command(workflow)
main.add_command(browser)

if __name__ == "__main__":
    main()
