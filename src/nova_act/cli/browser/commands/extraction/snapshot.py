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
"""Snapshot command — capture accessibility tree with sequential refs."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import TYPE_CHECKING

import click
import yaml

from nova_act.cli.browser.services.intent_resolution.snapshot import SnapshotElement, flatten_snapshot
from nova_act.cli.browser.utils.decorators import (
    browser_command_options,
    pack_command_params,
)
from nova_act.cli.browser.utils.error_handlers import handle_common_errors
from nova_act.cli.browser.utils.file_output import (
    OutputPathConfig,
    resolve_output_path,
    write_output_file,
)
from nova_act.cli.browser.utils.session import (
    command_session,
    get_active_page,
    prepare_session,
)
from nova_act.cli.core.output import echo_success

if TYPE_CHECKING:
    from nova_act.cli.browser.types import CommandParams

SNAPSHOT_OUTPUT = OutputPathConfig("snapshot", "yaml")

_DEFAULT_FUZZY_THRESHOLD = 70


def _parse_filter(filter_str: str) -> dict[str, object]:
    """Parse --filter JSON string and validate."""
    try:
        data: dict[str, object] = json.loads(filter_str)
    except json.JSONDecodeError as exc:
        raise click.BadParameter(f"Invalid JSON: {exc}") from exc
    if "keywords" not in data or not isinstance(data["keywords"], list):
        raise click.BadParameter("Filter must contain 'keywords' list")
    return data


def _fuzzy_match_elements(
    elements: list[SnapshotElement],
    keywords: list[str],
    threshold: int,
) -> list[dict[str, object]]:
    """Fuzzy match elements against keywords using rapidfuzz."""
    try:
        from rapidfuzz import fuzz
    except ImportError:
        # Fallback to simple substring matching
        matched: list[SnapshotElement] = []
        for el in elements:
            fields = [getattr(el, "name", ""), getattr(el, "role", ""), getattr(el, "value", "")]
            for kw in keywords:
                if any(kw.lower() in (f or "").lower() for f in fields):
                    matched.append(el)
                    break
        return [asdict(e) for e in matched]

    result: list[dict[str, object]] = []
    for el in elements:
        fields = [getattr(el, "name", "") or "", getattr(el, "role", "") or "", getattr(el, "value", "") or ""]
        for kw in keywords:
            if any(fuzz.token_set_ratio(kw, f) >= threshold for f in fields if f):
                result.append(asdict(el))
                break
    return result


@click.command()
@click.option("--output", "-o", help="Output file path (auto-generated if not specified)")
@click.option("--starting-page", help="Starting URL for new sessions (default: about:blank)")
@click.option(
    "--filter", "filter_str", default=None, help='Fuzzy filter: \'{"keywords": ["submit"], "threshold": 70}\''
)
@browser_command_options
@handle_common_errors
@pack_command_params
def snapshot(
    output: str | None,
    starting_page: str | None,
    filter_str: str | None,
    params: CommandParams,
) -> None:
    """Capture the accessibility tree of the current page.

    Returns a flattened list of elements with sequential refs (e1, e2, ...).
    Output is written to a YAML file (auto-generated or specified with --output).

    Examples:
        act browser snapshot
        act browser snapshot --output tree.yaml
        act browser snapshot --json
        act browser snapshot --filter '{"keywords": ["submit", "email"]}'
        act browser snapshot --session-id my-session
    """
    filter_config = _parse_filter(filter_str) if filter_str else None

    prep = prepare_session(params, starting_page)

    with command_session("snapshot", prep.manager, prep.session_info, params, log_args={"output": output}) as nova_act:
        output = resolve_output_path(output, SNAPSHOT_OUTPUT.filename, SNAPSHOT_OUTPUT.ext)
        tree = get_active_page(nova_act, prep.session_info).accessibility.snapshot()
        elements = flatten_snapshot(tree)
        records = [asdict(e) for e in elements]
        content = yaml.dump(records, default_flow_style=False, sort_keys=False)
        size = write_output_file(output, content)

    details: dict[str, object] = {
        "file": output,
        "size": size,
        "elements": len(records),
    }

    if filter_config:
        keywords = filter_config["keywords"]
        threshold = filter_config.get("threshold", _DEFAULT_FUZZY_THRESHOLD)
        if not isinstance(keywords, list) or not isinstance(threshold, int):
            raise click.BadParameter("Filter must contain 'keywords' list and optional 'threshold' int")
        matched = _fuzzy_match_elements(elements, keywords, threshold)
        details["filter"] = {"keywords": keywords, "threshold": threshold}
        details["matched_elements"] = matched
        details["matched_count"] = len(matched)

    echo_success(f"Snapshot saved to {output}", details=details)
