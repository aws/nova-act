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
"""Setup command for storing API key in local config."""

from __future__ import annotations

import click

from nova_act.cli.browser.utils.decorators import setup_command_options
from nova_act.cli.browser.utils.error_handlers import handle_common_errors
from nova_act.cli.core.config import (
    BrowserCliConfig,
    get_browser_cli_config_file,
    read_config,
    write_config,
)
from nova_act.cli.core.output import echo_success

# Minimum reasonable API key length
MIN_API_KEY_LENGTH = 10


def _validate_api_key(key: str) -> None:
    """Validate API key format. Raises click.ClickException on failure."""
    if len(key.strip()) < MIN_API_KEY_LENGTH:
        raise click.ClickException(f"Invalid API key format: key must be at least {MIN_API_KEY_LENGTH} characters.")


@click.command()
@click.option("--api-key", default=None, help="API key (non-interactive mode)")
@click.option("--aws-profile", default=None, help="Default AWS profile name for AWS auth")
@click.option("--aws-region", default=None, help="Default AWS region for AWS auth")
@click.option("--workflow-name", default=None, help="Default workflow definition name for AWS auth")
@click.option("--force", is_flag=True, default=False, help="Overwrite existing config without confirmation")
@click.option("--clear", is_flag=True, default=False, help="Remove all stored config")
@setup_command_options
@handle_common_errors
def setup(
    api_key: str | None,
    aws_profile: str | None,
    aws_region: str | None,
    workflow_name: str | None,
    force: bool,
    clear: bool,
    verbose: bool,
) -> None:
    """Store authentication config for persistent use.

    Stores settings in ~/.act_cli/browser/config.yaml so you don't need to pass
    flags for every command.

    Examples:
        act browser setup --api-key <your-key>
        act browser setup --aws-profile my-profile --aws-region us-west-2
        act browser setup --workflow-name my-workflow
        act browser setup --clear
    """
    if clear:
        config_file = get_browser_cli_config_file()
        if config_file.exists():
            config_file.unlink()
            echo_success("Config cleared", details={"config": str(config_file)})
        else:
            echo_success("No config file found — nothing to clear")
        return

    # If no flags provided, prompt for API key interactively
    if api_key is None and aws_profile is None and aws_region is None and workflow_name is None:
        api_key = click.prompt("Enter your Nova Act API key", hide_input=True)

    if api_key is not None:
        _validate_api_key(api_key)

    # Read existing config and merge
    config = read_config() if get_browser_cli_config_file().exists() else BrowserCliConfig()

    if api_key is not None:
        if config.api_key is not None and not force:
            if not click.confirm("API key already configured. Overwrite?"):
                raise click.Abort()
        config.api_key = api_key.strip()
    if aws_profile is not None:
        config.aws_profile = aws_profile
    if aws_region is not None:
        config.aws_region = aws_region
    if workflow_name is not None:
        config.workflow_name = workflow_name

    write_config(config)
    stored = {k: v for k, v in vars(config).items() if v is not None}
    echo_success("Config saved", details={"config": str(get_browser_cli_config_file()), **stored})
