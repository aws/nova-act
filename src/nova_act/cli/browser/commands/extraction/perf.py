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
"""Perf command for collecting and displaying browser performance metrics."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import click

from nova_act.cli.browser.services.performance_collector import (
    PerfData,
    PerformanceCollector,
    format_memory,
    format_navigation,
    format_paint,
    format_resources,
    format_vitals,
)
from nova_act.cli.browser.utils.decorators import (
    browser_command_options,
    pack_command_params,
)
from nova_act.cli.browser.utils.error_handlers import handle_common_errors
from nova_act.cli.browser.utils.file_output import (
    OutputPathConfig,
    validate_output_dir,
    write_output_file,
)
from nova_act.cli.browser.utils.session import (
    command_session,
    get_active_page,
    prepare_session,
)
from nova_act.cli.core.cli_stdout import get_cli_stdout
from nova_act.cli.core.json_output import is_json_mode
from nova_act.cli.core.output import echo_success

if TYPE_CHECKING:
    from nova_act.cli.browser.types import CommandParams

PERF_OUTPUT = OutputPathConfig("perf", "json")

METRIC_CHOICES = ["navigation", "resources", "vitals", "memory", "all"]


@click.command(name="perf")
@click.option(
    "--metrics",
    type=click.Choice(METRIC_CHOICES, case_sensitive=False),
    default="all",
    show_default=True,
    help="Which metrics to collect",
)
@click.option("--output", "-o", help="Save full metrics to JSON file")
@browser_command_options
@handle_common_errors
@pack_command_params
def perf(
    metrics: str,
    output: str | None,
    params: CommandParams,
) -> None:
    """Collect and display browser performance metrics.

    Collects Navigation Timing, Resource Timing, Core Web Vitals (LCP, CLS),
    and Memory usage via the browser Performance API.

    \b
    Examples:
        act browser perf
        act browser perf --metrics vitals
        act browser perf --metrics navigation --json
        act browser perf --output report.json
    """
    if output:
        validate_output_dir(output)

    prep = prepare_session(params, None)

    with command_session(
        "perf",
        prep.manager,
        prep.session_info,
        params,
        log_args={"metrics": metrics, "output": output},
    ) as nova_act:
        collector = PerformanceCollector(get_active_page(nova_act, prep.session_info))
        data = collector.collect_all()

        # Filter to requested metrics
        filtered = _filter_metrics(data, metrics)

        if output:
            write_output_file(output, json.dumps(filtered, indent=2))

        details: dict[str, object] = {}
        if output:
            details["File"] = output
        if is_json_mode():
            details["data"] = filtered

        echo_success("Performance metrics collected", details=details)

        if not is_json_mode():
            _print_human_readable(data, metrics)


def _filter_metrics(data: PerfData, metrics: str) -> dict[str, object]:
    """Return only the requested metric categories."""
    if metrics == "all":
        return dict(data)
    return {metrics: data.get(metrics)}


def _print_human_readable(data: PerfData, metrics: str) -> None:
    """Print formatted performance report to stdout."""
    stdout = get_cli_stdout()
    sections: list[tuple[str, list[str]]] = []

    if metrics in ("all", "navigation"):
        sections.append(("Navigation Timing", format_navigation(data.get("navigation"))))
        sections.append(("Paint Timing", format_paint(data.get("paint", []))))
    if metrics in ("all", "resources"):
        sections.append(("Resources", format_resources(data.get("resources", []))))
    if metrics in ("all", "vitals"):
        vitals = data.get("vitals")
        if vitals:
            sections.append(("Core Web Vitals", format_vitals(vitals)))
    if metrics in ("all", "memory"):
        sections.append(("Memory", format_memory(data.get("memory"))))

    click.echo("", file=stdout)
    for title, lines in sections:
        click.echo(f"  {title}", file=stdout)
        for line in lines:
            click.echo(line, file=stdout)
        click.echo("", file=stdout)
