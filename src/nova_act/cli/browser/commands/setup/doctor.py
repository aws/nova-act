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
"""Doctor command for diagnosing browser CLI environment health."""

import click

from nova_act.cli.browser.commands.setup.cli_doctor import CLIDoctor
from nova_act.cli.browser.utils.decorators import setup_command_options
from nova_act.cli.browser.utils.error_handlers import handle_common_errors


@click.command()
@setup_command_options
@handle_common_errors
def doctor(verbose: bool) -> None:
    """Run diagnostic checks on the browser CLI environment.

    Checks Chrome installation, API key, session directory, and Playwright.

    Examples:
        act browser doctor
        act browser doctor --json
    """
    CLIDoctor().run(verbose)
