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
"""Gherkin-to-CLI plan compiler — parses .feature files into executable command plans."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from gherkin.parser import Parser
from gherkin.parser_types import GherkinDocument, Scenario, ScenarioEnvelope, Step
from gherkin.token_scanner import TokenScanner

# URL pattern for Given steps that should map to navigate
_URL_PATTERN = re.compile(r"""['"]?(https?://\S+?)['"]?\s*$""")

# Keywords that flag human auth requirement
_AUTH_KEYWORDS = re.compile(
    r"\b(log\s*in|sign\s*in|authenticate|mfa|captcha|two.factor|2fa|otp|password)\b",
    re.IGNORECASE,
)


@dataclass
class PlanStep:
    """A single compiled step in the execution plan."""

    type: str  # navigate, action, assertion
    cli: str
    source_steps: list[str]
    requires: str | None = None
    note: str | None = None


@dataclass
class ScenarioPlan:
    """Compiled plan for a single scenario."""

    name: str
    tags: list[str]
    steps: list[PlanStep]

    @property
    def requires_human_auth(self) -> bool:
        return any(s.requires == "human_auth" for s in self.steps)


@dataclass
class FeaturePlan:
    """Compiled plan for an entire feature file."""

    feature: str
    source_file: str
    plan_strategy: str
    scenarios: list[ScenarioPlan] = field(default_factory=list)


def _resolve_keyword(keyword_type: str, prev_keyword_type: str | None) -> str:
    """Resolve And/But to the previous keyword type."""
    if keyword_type == "Conjunction" and prev_keyword_type:
        return prev_keyword_type
    return keyword_type


def _step_type(keyword_type: str) -> str:
    """Map resolved Gherkin keyword type to plan step type."""
    if keyword_type == "Outcome":
        return "assertion"
    return "action"


def _detect_navigate(keyword_type: str, text: str) -> str | None:
    """If this is a Given step with a URL, return the URL. Otherwise None."""
    if keyword_type != "Context":
        return None
    m = _URL_PATTERN.search(text)
    return m.group(1) if m else None


def _detect_auth(text: str) -> str | None:
    """Return 'human_auth' if step text contains auth-related keywords."""
    return "human_auth" if _AUTH_KEYWORDS.search(text) else None


def _build_cli(step_type: str, text: str, url: str | None = None) -> str:
    """Build the CLI command string for a step."""
    if url:
        return f"act browser goto '{url}'"
    if step_type == "assertion":
        return f'act browser verify "{text}"'
    return f'act browser execute "{text}"'


def _compile_steps_conservative(resolved_steps: list[tuple[str, str, str]]) -> list[PlanStep]:
    """Conservative strategy: 1:1 mapping from Gherkin steps to CLI commands."""
    plan_steps: list[PlanStep] = []
    for keyword_type, keyword_text, text in resolved_steps:
        url = _detect_navigate(keyword_type, text)
        stype = "navigate" if url else _step_type(keyword_type)
        source = f"{keyword_text.strip()} {text}"
        auth = _detect_auth(text)
        plan_steps.append(
            PlanStep(
                type=stype,
                cli=_build_cli(stype, text, url),
                source_steps=[source],
                requires=auth,
                note="Login may require MFA or CAPTCHA" if auth else None,
            )
        )
    return plan_steps


def _group_consecutive_steps(resolved_steps: list[tuple[str, str, str]]) -> list[list[tuple[str, str, str]]]:
    """Group consecutive steps of the same resolved type, splitting on navigate steps or type changes."""
    groups: list[list[tuple[str, str, str]]] = []
    current_group: list[tuple[str, str, str]] = [resolved_steps[0]]

    for kw_type, kw_text, text in resolved_steps[1:]:
        prev_type = current_group[0][0]
        url = _detect_navigate(kw_type, text)
        prev_url = _detect_navigate(prev_type, current_group[0][2])
        if url or prev_url or kw_type != prev_type:
            groups.append(current_group)
            current_group = [(kw_type, kw_text, text)]
        else:
            current_group.append((kw_type, kw_text, text))
    groups.append(current_group)
    return groups


def _compile_steps_aggressive(resolved_steps: list[tuple[str, str, str]]) -> list[PlanStep]:
    """Aggressive strategy: collapse sequential same-type steps into single commands."""
    if not resolved_steps:
        return []

    plan_steps: list[PlanStep] = []
    groups = _group_consecutive_steps(resolved_steps)

    for group in groups:
        first_kw_type, _, first_text = group[0]
        url = _detect_navigate(first_kw_type, first_text)
        stype = "navigate" if url else _step_type(first_kw_type)
        sources = [f"{kw.strip()} {t}" for _, kw, t in group]

        if len(group) == 1:
            combined_text = first_text
        else:
            # Collapse texts with commas + "and"
            texts = [t for _, _, t in group]
            combined_text = ", ".join(texts[:-1]) + ", and " + texts[-1] if len(texts) > 2 else " and ".join(texts)

        auth = _detect_auth(combined_text)
        plan_steps.append(
            PlanStep(
                type=stype,
                cli=_build_cli(stype, combined_text, url),
                source_steps=sources,
                requires=auth,
                note="Login may require MFA or CAPTCHA" if auth else None,
            )
        )
    return plan_steps


def _expand_outline(scenario: Scenario) -> list[Scenario]:
    """Expand a Scenario Outline into concrete scenarios from Examples table."""
    examples_list = scenario.get("examples", [])
    if not examples_list:
        return [scenario]

    template_steps = scenario.get("steps", [])
    expanded: list[Scenario] = []

    for examples in examples_list:
        header = examples.get("tableHeader")
        columns = [c["value"] for c in header["cells"]] if header else []
        rows = examples.get("tableBody", [])

        for row in rows:
            values = [c["value"] for c in row.get("cells", [])]
            param_map = dict(zip(columns, values, strict=True))

            # Substitute <param> in step text and scenario name
            name = scenario.get("name", "")
            for k, v in param_map.items():
                name = name.replace(f"<{k}>", v)

            concrete_steps: list[Step] = []
            for step in template_steps:
                new_text = step["text"]
                for k, v in param_map.items():
                    new_text = new_text.replace(f"<{k}>", v)
                concrete_steps.append({**step, "text": new_text})

            expanded.append(
                {
                    **scenario,
                    "name": name,
                    "steps": concrete_steps,
                    "examples": [],
                    "keyword": "Scenario",
                }
            )
    return expanded


def compile_feature(
    feature_path: str | Path, strategy: str = "aggressive", tags: list[str] | None = None
) -> FeaturePlan:
    """Compile a .feature file into an execution plan.

    Args:
        feature_path: Path to the .feature file.
        strategy: 'aggressive' (collapse steps) or 'conservative' (1:1 mapping).
        tags: Optional list of tags to filter scenarios (e.g. ['@smoke']).

    Returns:
        FeaturePlan with compiled scenarios.
    """
    path = Path(feature_path)
    parser = Parser()
    gherkin_doc: GherkinDocument = parser.parse(TokenScanner(path.read_text()))
    feature = gherkin_doc.get("feature")
    if not feature:
        return FeaturePlan(feature="", source_file=str(path), plan_strategy=strategy)

    plan = FeaturePlan(
        feature=feature["name"],
        source_file=str(path),
        plan_strategy=strategy,
    )

    compile_fn = _compile_steps_aggressive if strategy == "aggressive" else _compile_steps_conservative

    for child in feature.get("children", []):
        scenario = cast(ScenarioEnvelope, child).get("scenario")
        if not scenario:
            continue

        # Expand Scenario Outline
        concrete_scenarios = _expand_outline(scenario) if scenario.get("examples") else [scenario]

        for sc in concrete_scenarios:
            sc_tags = [t["name"] for t in sc.get("tags", [])]
            # Inherit feature-level tags
            feature_tags = [t["name"] for t in feature.get("tags", [])]
            all_tags = list(set(feature_tags + sc_tags))

            # Tag filtering
            if tags and not any(t in all_tags for t in tags):
                continue

            # Resolve And/But keywords
            resolved: list[tuple[str, str, str]] = []
            prev_kw_type: str | None = None
            for step in sc.get("steps", []):
                kw_type = _resolve_keyword(step["keywordType"], prev_kw_type)
                if kw_type != "Conjunction":
                    prev_kw_type = kw_type
                resolved.append((kw_type, step["keyword"], step["text"]))

            steps = compile_fn(resolved)
            plan.scenarios.append(ScenarioPlan(name=sc["name"], tags=all_tags, steps=steps))

    return plan
