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
"""Click decorators for browser CLI commands."""

import functools
from collections.abc import Callable
from typing import TypeVar

import click

from nova_act.cli.core.json_output import set_json_mode

F = TypeVar("F", bound=Callable[..., object])  # type: ignore[explicit-any]


def common_session_options(func: F) -> F:  # type: ignore[explicit-any]
    """Add common session-related options to a Click command."""
    func = click.option(
        "--nova-arg",
        multiple=True,
        help="Pass additional NovaAct parameters as KEY=VALUE (repeatable). "
        "Examples: --nova-arg max_steps=5 --nova-arg screen_width=1920. "
        "Supports constructor args (headless, screen_width, screen_height) "
        "and method args (max_steps, model_temperature, observation_delay_ms).",
    )(func)
    func = click.option("--session-id", default="default", help="Session ID (default: 'default')")(func)
    return func


def auth_options(func: F) -> F:  # type: ignore[explicit-any]
    """Add authentication options to a Click command.

    Adds --auth-mode, --profile, --region, and --workflow-name options.
    Apply AFTER common_session_options in the decorator stack.
    """
    func = click.option(
        "--workflow-name",
        default=None,
        help="Workflow definition name for AWS auth (default: 'act-cli')",
    )(func)
    func = click.option(
        "--region",
        default=None,
        help="AWS region for AWS auth (default: us-east-1)",
    )(func)
    func = click.option(
        "--aws-profile",
        "profile",
        default=None,
        help="AWS profile name for AWS auth",
    )(func)
    func = click.option(
        "--auth-mode",
        type=click.Choice(["api-key", "aws"]),
        default=None,
        help="Authentication mode (auto-detected if not specified)",
    )(func)
    return func


def common_browser_options(func: F) -> F:  # type: ignore[explicit-any]
    """Add common browser configuration options to a Click command."""
    func = click.option(
        "--user-data-dir",
        default=None,
        help="Working directory for Chrome profile (auto-created if not specified with --use-default-chrome)",
    )(func)
    func = click.option(
        "--use-default-chrome",
        is_flag=True,
        default=False,
        help="Use default Chrome browser with extensions (quits running Chrome, rsyncs profile)",
    )(func)
    func = click.option(
        "--launch-arg",
        multiple=True,
        help="Additional Chrome launch argument (repeatable, e.g. --launch-arg=--ignore-certificate-errors)",
    )(func)
    func = click.option(
        "--ignore-https-errors/--no-ignore-https-errors",
        default=True,
        help="Ignore HTTPS certificate errors (enabled by default)",
    )(func)
    func = click.option(
        "--browser-profile-path",
        "profile_path",
        help="Path to browser profile directory for persistent sessions",
    )(func)
    func = click.option(
        "--executable-path",
        help="Path to custom Chromium-based browser executable",
    )(func)
    func = click.option(
        "--headed",
        is_flag=True,
        default=False,
        help="Launch browser in headed mode (visible UI)",
    )(func)
    func = click.option(
        "--headless",
        is_flag=True,
        default=False,
        help="Launch browser in headless mode (no visible UI)",
    )(func)
    func = click.option(
        "--cdp",
        default=None,
        help="Connect to an existing browser via CDP endpoint URL (e.g. ws://localhost:9222/devtools/browser/...)",
    )(func)
    return func


def json_option(func: F) -> F:  # type: ignore[explicit-any]
    """Add --json flag that enables structured JSON output mode."""

    def _set_json_mode(ctx: click.Context, param: click.Parameter, value: bool) -> None:  # noqa: ARG001
        if value:
            set_json_mode(True)

    return click.option(
        "--json",
        "json_flag",
        is_flag=True,
        default=False,
        is_eager=True,
        expose_value=False,
        callback=_set_json_mode,
        help="Output results as structured JSON",
    )(func)


def quiet_option(func: F) -> F:  # type: ignore[explicit-any]
    """Add --quiet/-q flag to suppress SDK stdout output during execution."""
    return click.option(
        "--quiet",
        "-q",
        is_flag=True,
        default=False,
        help="Suppress SDK output for token efficiency (use with --json for minimal output)",
    )(func)


def verbose_option(func: F) -> F:  # type: ignore[explicit-any]
    """Add --verbose/-v flag for human-friendly decorated output with full SDK trace."""
    return click.option(
        "--verbose",
        "-v",
        is_flag=True,
        default=False,
        help="Show decorated output with full SDK trace for interactive debugging",
    )(func)


def browser_command_options(func: F) -> F:  # type: ignore[explicit-any]
    """Composite decorator for all browser commands (browsing/ + extraction/).

    Combines: common_browser_options, common_session_options, auth_options,
    json_option, quiet_option, verbose_option, no_screenshot_on_failure — in the correct Click application order.
    """
    func = click.option(
        "--observe",
        is_flag=True,
        default=False,
        help="After command completes, describe the current page layout",
    )(func)
    func = click.option(
        "--no-screenshot",
        is_flag=True,
        default=False,
        help="Skip automatic screenshot capture after command completes",
    )(func)
    func = click.option(
        "--no-snapshot",
        is_flag=True,
        default=False,
        help="Skip automatic accessibility snapshot after command completes",
    )(func)
    func = click.option(
        "--no-screenshot-on-failure",
        is_flag=True,
        default=False,
        help="Disable automatic screenshot capture on act() failure",
    )(func)
    func = verbose_option(func)
    func = quiet_option(func)
    func = json_option(func)
    func = auth_options(func)
    func = common_session_options(func)
    func = common_browser_options(func)
    return func


def setup_command_options(func: F) -> F:  # type: ignore[explicit-any]
    """Composite decorator for setup/diagnostic commands (doctor, setup).

    Combines: json_option, verbose_option.
    """
    func = verbose_option(func)
    func = json_option(func)
    return func


def pack_command_params(func: F) -> F:  # type: ignore[explicit-any]
    """Decorator that packs shared CLI kwargs into a CommandParams object.

    Place AFTER @handle_common_errors (innermost) so it runs before error handling.
    Extracts the ~16 shared kwargs injected by @browser_command_options, creates
    a CommandParams instance, and passes it as ``params`` to the wrapped function.
    """
    from nova_act.cli.browser.types import COMMAND_PARAM_FIELDS, CommandParams

    @functools.wraps(func)
    def wrapper(*args: object, **kwargs: object) -> object:
        param_kwargs = {k: kwargs.pop(k) for k in list(kwargs) if k in COMMAND_PARAM_FIELDS}
        kwargs["params"] = CommandParams(**param_kwargs)  # type: ignore[arg-type]
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]
