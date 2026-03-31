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
"""Browser command group for Nova Act CLI."""

import click

from nova_act.cli.browser.commands import (
    ask,
    back,
    click_target,
    console_log,
    diff,
    doctor,
    evaluate,
    execute,
    extract,
    fill_form,
    forward,
    get_content,
    goto,
    network_log,
    page,
    pdf,
    perf,
    qa_plan,
    query,
    refresh,
    screenshot,
    scroll_to,
    snapshot,
    style,
    tab_close,
    tab_list,
    tab_new,
    tab_select,
    type_text,
    verify,
    wait_for,
)
from nova_act.cli.browser.commands.session import session
from nova_act.cli.browser.commands.setup.setup import setup
from nova_act.cli.group import StyledGroup


@click.group(cls=StyledGroup)
def browser() -> None:
    """Interactive browser automation commands.

    Execute browser actions using natural language prompts or specific commands.

    Examples:
        act browser execute "Click the login button"
        act browser goto https://example.com
        act browser screenshot --output output.png
    """
    pass


# Register commands in desired order
browser.add_command(ask)
browser.add_command(back)
browser.add_command(console_log)
browser.add_command(diff)
browser.add_command(click_target)
browser.add_command(doctor)
browser.add_command(evaluate)
browser.add_command(execute)
browser.add_command(forward)
browser.add_command(goto)
browser.add_command(fill_form)
browser.add_command(network_log)
browser.add_command(page)
browser.add_command(pdf)
browser.add_command(perf)
browser.add_command(qa_plan)
browser.add_command(screenshot)
browser.add_command(scroll_to)
browser.add_command(setup)
browser.add_command(snapshot)
browser.add_command(extract)
browser.add_command(get_content)
browser.add_command(query)
browser.add_command(refresh)
browser.add_command(session)
browser.add_command(style)
browser.add_command(tab_close)
browser.add_command(tab_list)
browser.add_command(tab_new)
browser.add_command(tab_select)
browser.add_command(type_text)
browser.add_command(verify)
browser.add_command(wait_for)
