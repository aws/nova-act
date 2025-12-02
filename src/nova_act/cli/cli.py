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
from nova_act.cli.core.theme import ThemeName, set_active_theme
from nova_act.cli.group import StyledGroup
from nova_act.cli.workflow.commands import create, delete, deploy, run, show, update
from nova_act.cli.workflow.commands.list import list


@click.group(cls=StyledGroup)
@click.option("--profile", help="AWS profile to use (from ~/.aws/credentials)")
@click.pass_context
def workflow(ctx: click.Context, profile: str | None) -> None:
    """Workflow management commands."""
    if profile:
        os.environ["AWS_PROFILE"] = profile


# Add all commands to workflow group in desired order
workflow.add_command(create.create)
workflow.add_command(update.update)
workflow.add_command(delete.delete)
workflow.add_command(show.show)
workflow.add_command(deploy.deploy)
workflow.add_command(run.run)
workflow.add_command(list)


@click.group(cls=StyledGroup)
@click.version_option(version=VERSION)
@click.option("--no-color", is_flag=True, help="Disable colored output")
def main(no_color: bool) -> None:
    """Nova Act CLI."""
    if no_color:
        set_active_theme(ThemeName.NONE)


main.add_command(workflow)

if __name__ == "__main__":
    main()
