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
"""qa-plan command — compile Gherkin .feature files into CLI execution plans."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import click

from nova_act.cli.browser.utils.decorators import json_option
from nova_act.cli.core.output import echo_success, exit_with_error, get_cli_stdout


@click.command(name="qa-plan")
@click.argument("feature_file", type=click.Path(exists=True))
@click.option(
    "--plan-strategy",
    type=click.Choice(["aggressive", "conservative"]),
    default="aggressive",
    show_default=True,
    help="aggressive collapses sequential same-type steps; conservative maps 1:1",
)
@click.option("--tags", multiple=True, help="Filter scenarios by @tag (repeatable)")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save plan to file")
@click.option("--dry-run", is_flag=True, help="Show plan summary without full JSON output")
@json_option
def qa_plan(feature_file: str, plan_strategy: str, tags: tuple[str, ...], output: str | None, dry_run: bool) -> None:
    """Compile a Gherkin .feature file into a CLI execution plan.

    Parses FEATURE_FILE and produces a JSON plan mapping Gherkin steps to
    Nova Act CLI commands. The plan is consumed by an agent — qa-plan does
    NOT execute anything.

    Keyword mapping:
      Given + URL → act browser goto
      Given/When  → act browser execute
      Then        → act browser verify

    Examples:
        act browser qa-plan tests/smoke.feature
        act browser qa-plan tests/login.feature --plan-strategy conservative
        act browser qa-plan tests/ --tags @smoke --tags @regression
        act browser qa-plan tests/checkout.feature --output plan.json
        act browser qa-plan tests/smoke.feature --dry-run
    """
    from nova_act.cli.browser.services.gherkin_compiler import compile_feature

    path = Path(feature_file)

    # Collect .feature files
    if path.is_dir():
        files = sorted(path.rglob("*.feature"))
        if not files:
            exit_with_error(
                "No .feature files found",
                f"No .feature files in {path}",
                suggestions=["Check the path contains .feature files"],
            )
            return
    else:
        files = [path]

    tag_list = list(tags) if tags else None
    plans = []
    for f in files:
        plan = compile_feature(f, strategy=plan_strategy, tags=tag_list)
        if plan.scenarios:
            d = asdict(plan)
            # Add computed property that asdict() doesn't serialize
            for sc_dict, sc_obj in zip(d["scenarios"], plan.scenarios):
                sc_dict["requires_human_auth"] = sc_obj.requires_human_auth
            plans.append(d)

    if not plans:
        exit_with_error(
            "No matching scenarios",
            "No scenarios matched the given tag filters",
            suggestions=["Check your --tags filter"],
        )
        return

    result = plans[0] if len(plans) == 1 else {"plans": plans, "total_features": len(plans)}

    if dry_run:
        total_scenarios = sum(len(p.get("scenarios", [])) for p in (plans if isinstance(plans, list) else [result]))
        total_steps = sum(
            len(s.get("steps", []))
            for p in (plans if isinstance(plans, list) else [result])
            for s in p.get("scenarios", [])
        )
        echo_success(
            "Plan compiled (dry-run)",
            details={
                "features": len(plans),
                "scenarios": total_scenarios,
                "steps": total_steps,
                "strategy": plan_strategy,
            },
        )
        return

    serialized = json.dumps(result, indent=2)

    if output:
        Path(output).write_text(serialized, encoding="utf-8")
        echo_success(
            f"Plan saved to {output}",
            details={
                "features": len(plans),
                "scenarios": sum(len(p.get("scenarios", [])) for p in plans),
            },
        )
    else:
        out = get_cli_stdout()
        click.echo(serialized, file=out)
