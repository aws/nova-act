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
"""Page Playwright passthrough command for direct page API access."""

from __future__ import annotations

import asyncio
import inspect
import json
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from nova_act.cli.browser.types import CommandParams

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
from nova_act.cli.core.output import echo_success, get_cli_stdout

BLOCKED_METHODS: frozenset[str] = frozenset({"close"})


def _get_page_signatures(page: object) -> str:
    """Introspect the page object and return method signatures with type hints."""
    lines: list[str] = []
    for name in sorted(dir(page)):
        if name.startswith("_"):
            continue
        if name in BLOCKED_METHODS:
            continue
        attr = getattr(page, name, None)
        if attr is None or not callable(attr):
            continue
        try:
            sig = inspect.signature(attr)
            lines.append(f"{name}{sig}")
        except (ValueError, TypeError):
            lines.append(name)
    return "\n".join(lines)


def _call_method(page: object, method_name: str, kwargs: dict[str, object]) -> object:
    """Call a method on the page object, awaiting if it returns a coroutine."""
    method = getattr(page, method_name)
    result = method(**kwargs)
    if asyncio.iscoroutine(result):
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(result)
        loop.close()
    return result


@click.command()
@click.argument("method_name", required=False, default=None)
@click.option("--kwargs", "kwargs_json", default=None, help="JSON string of keyword arguments for the method")
@click.option("--signatures", is_flag=True, default=False, help="List available page methods with type hints")
@click.option("--starting-page", help="Starting URL for new sessions (default: about:blank)")
@browser_command_options
@handle_common_errors
@pack_command_params
def page(
    method_name: str | None,
    kwargs_json: str | None,
    signatures: bool,
    starting_page: str | None,
    params: CommandParams,
) -> None:
    """Call any method on the Playwright page object directly.

    Provides full passthrough access to the Playwright page API. Use --signatures
    to discover available methods.

    Examples:
        act browser page go_back --session-id my-session
        act browser page reload --session-id my-session
        act browser page goto --kwargs '{"url": "https://example.com"}'
        act browser page set_viewport_size --kwargs '{"viewport_size": {"width": 1920, "height": 1080}}'
        act browser page --signatures
    """
    prep = prepare_session(params, starting_page)

    with command_session(
        "page", prep.manager, prep.session_info, params, log_args={"method_name": method_name}
    ) as nova_act:
        active_page = get_active_page(nova_act, prep.session_info)
        if signatures:
            sig_output = _get_page_signatures(active_page)
            click.echo(sig_output, file=get_cli_stdout())
            return

        if not method_name:
            raise click.UsageError("method_name is required unless --signatures is used")

        if method_name in BLOCKED_METHODS:
            raise click.UsageError(
                f"Method '{method_name}' is blocked for safety. "
                f"Blocked methods: {', '.join(sorted(BLOCKED_METHODS))}"
            )

        if not hasattr(active_page, method_name):
            raise click.UsageError(f"Unknown page method: {method_name}")

        kwargs: dict[str, object] = {}
        if kwargs_json:
            try:
                kwargs = json.loads(kwargs_json)
            except json.JSONDecodeError as e:
                raise click.UsageError(f"Invalid JSON in --kwargs: {e}") from e
            if not isinstance(kwargs, dict):
                raise click.UsageError("--kwargs must be a JSON object")

        result = _call_method(active_page, method_name, kwargs)

        details: dict[str, object] = {}
        if result is not None:
            details["Result"] = str(result)

        echo_success("Page method called", details=details)
