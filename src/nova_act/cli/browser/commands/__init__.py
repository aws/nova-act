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
"""Browser commands module.

Note: ``session`` and ``setup`` Click commands are NOT re-exported here.
Re-exporting them shadows the subpackage names (``commands.session``,
``commands.setup``), which breaks ``unittest.mock.patch()`` on Python 3.10
because ``mock._dot_lookup`` resolves the Click object instead of the module.
Import these commands directly from their submodules instead.
"""

__all__ = [
    "ask",
    "back",
    "click_target",
    "console_log",
    "diff",
    "doctor",
    "evaluate",
    "execute",
    "extract",
    "fill_form",
    "forward",
    "get_content",
    "goto",
    "network_log",
    "page",
    "pdf",
    "perf",
    "qa_plan",
    "query",
    "refresh",
    "screenshot",
    "scroll_to",
    "snapshot",
    "style",
    "tab_close",
    "tab_list",
    "tab_new",
    "tab_select",
    "type_text",
    "verify",
    "wait_for",
]

from nova_act.cli.browser.commands.browsing.ask import ask
from nova_act.cli.browser.commands.browsing.back import back
from nova_act.cli.browser.commands.browsing.click_target import click_target
from nova_act.cli.browser.commands.browsing.console_log import console_log
from nova_act.cli.browser.commands.browsing.execute import execute
from nova_act.cli.browser.commands.browsing.fill_form import fill_form
from nova_act.cli.browser.commands.browsing.forward import forward
from nova_act.cli.browser.commands.browsing.goto import goto
from nova_act.cli.browser.commands.browsing.network_log import network_log
from nova_act.cli.browser.commands.browsing.page import page
from nova_act.cli.browser.commands.browsing.refresh import refresh
from nova_act.cli.browser.commands.browsing.scroll_to import scroll_to
from nova_act.cli.browser.commands.browsing.tab_close import tab_close
from nova_act.cli.browser.commands.browsing.tab_list import tab_list
from nova_act.cli.browser.commands.browsing.tab_new import tab_new
from nova_act.cli.browser.commands.browsing.tab_select import tab_select
from nova_act.cli.browser.commands.browsing.type_text import type_text
from nova_act.cli.browser.commands.browsing.verify import verify
from nova_act.cli.browser.commands.browsing.wait_for import wait_for
from nova_act.cli.browser.commands.extraction.diff import diff
from nova_act.cli.browser.commands.extraction.evaluate import evaluate
from nova_act.cli.browser.commands.extraction.extract import extract
from nova_act.cli.browser.commands.extraction.get_content import get_content
from nova_act.cli.browser.commands.extraction.pdf import pdf
from nova_act.cli.browser.commands.extraction.perf import perf
from nova_act.cli.browser.commands.extraction.query import query
from nova_act.cli.browser.commands.extraction.screenshot import screenshot
from nova_act.cli.browser.commands.extraction.snapshot import snapshot
from nova_act.cli.browser.commands.extraction.style import style
from nova_act.cli.browser.commands.setup.doctor import doctor
from nova_act.cli.browser.commands.setup.qa_plan import qa_plan
