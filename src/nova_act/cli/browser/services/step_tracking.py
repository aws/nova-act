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
"""Step tracking — monkey-patch NovaAct for per-step a11y snapshots + steps summary writer."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

import yaml

if TYPE_CHECKING:
    from nova_act import NovaAct
    from nova_act.cli.browser.services.intent_resolution.snapshot import SnapshotElement


# ---------------------------------------------------------------------------
# TypedDicts for the trajectory JSON written by the SDK's run_info_compiler.
# The SDK has no exported types for this format, so we define them CLI-side.
# ---------------------------------------------------------------------------


class TrajectoryCall(TypedDict):
    """A single call within a step's program."""

    name: str
    kwargs: dict[str, object]


class TrajectoryProgram(TypedDict):
    """The program executed during a single step."""

    calls: list[TrajectoryCall]


class _TrajectoryStepRequired(TypedDict):
    """Required fields for a trajectory step."""

    program: TrajectoryProgram


class TrajectoryStep(_TrajectoryStepRequired, total=False):
    """A single step in the trajectory. ``active_url`` is optional in the JSON."""

    active_url: str


class TrajectoryMetadata(TypedDict, total=False):
    """Top-level metadata block in the trajectory JSON."""

    time_worked_s: float


class TrajectoryData(TypedDict, total=False):
    """Top-level trajectory JSON structure."""

    steps: list[TrajectoryStep]
    metadata: TrajectoryMetadata


logger = logging.getLogger(__name__)


def patch_nova_act_for_step_snapshots(nova_act: NovaAct, snapshots_out: list[list[SnapshotElement]]) -> None:
    """Monkey-patch NovaAct to capture a11y tree between act() steps.

    NOTE: This SHOULD be a proper SDK hook (e.g. on_step_complete callback).
    Monkey-patching is a stopgap until the SDK exposes a first-class extension point.

    Patches the dispatcher's program runner to capture an accessibility snapshot
    after each program execution (i.e. after each step). Snapshots accumulate in
    ``snapshots_out`` (passed by reference). Snapshot failure never breaks act().
    """
    try:
        runner = nova_act.dispatcher._program_runner
    except AttributeError:
        logger.debug("Cannot patch NovaAct — dispatcher or _program_runner not found")
        return

    original_run = runner.run

    def _patched_run(program, *args, **kwargs):  # type: ignore[no-untyped-def]
        result = original_run(program, *args, **kwargs)
        try:
            from nova_act.cli.browser.services.intent_resolution.snapshot import (
                flatten_snapshot,
            )

            tree = nova_act.page.accessibility.snapshot()
            snapshots_out.append(flatten_snapshot(tree))
        except Exception:
            logger.debug("Step snapshot capture failed", exc_info=True)
        return result

    runner.run = _patched_run  # type: ignore[method-assign]


def write_steps_summary(
    trajectory_dir: Path,
    command_name: str,
    snapshots: list[list[SnapshotElement]],
    log_dir: Path,
) -> dict[str, object] | None:
    """Parse trajectory JSON, merge with monkey-patch snapshots, write steps summary.

    Args:
        trajectory_dir: Directory containing SDK trajectory files.
        command_name: Name of the command (unused, kept for API compat).
        snapshots: Per-step a11y snapshots from monkey-patch.
        log_dir: Per-command subdirectory to write steps.yaml into.

    Returns ``{"steps_taken": N, "time_worked_s": T, "steps_path": path}`` or None on failure.
    """
    try:
        trajectory_file = _find_latest_trajectory(trajectory_dir)
        if trajectory_file is None:
            logger.debug("No trajectory file found in %s", trajectory_dir)
            return None

        trajectory = json.loads(trajectory_file.read_text())
        steps_data = _extract_steps(trajectory)
        step_transitions = _compute_step_transitions(snapshots)

        # Merge transitions into steps
        for step_num, diff in step_transitions.items():
            idx = step_num - 1  # step_num is 1-based
            if 0 <= idx < len(steps_data):
                steps_data[idx]["transition"] = diff

        metadata = trajectory.get("metadata", {})
        time_worked: float = 0.0
        if isinstance(metadata, dict):
            raw_time = metadata.get("time_worked_s")
            if isinstance(raw_time, (int, float)):
                time_worked = float(raw_time)
        summary = {
            "steps_taken": len(steps_data),
            "time_worked_s": round(time_worked, 1),
            "steps": steps_data,
        }

        log_dir.mkdir(parents=True, exist_ok=True)
        steps_path = log_dir / "steps.yaml"
        steps_path.write_text(yaml.dump(summary, default_flow_style=False, sort_keys=False))

        return {
            "steps_taken": len(steps_data),
            "time_worked_s": round(time_worked, 1),
            "steps_path": str(steps_path),
        }
    except Exception:
        logger.debug("Failed to write steps summary", exc_info=True)
        return None


def _find_latest_trajectory(directory: Path) -> Path | None:
    """Find the most recently modified trajectory JSON in *directory* (recursive)."""
    candidates = sorted(directory.rglob("*trajectory*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _extract_steps(trajectory: dict[str, object]) -> list[dict[str, object]]:
    """Extract action/detail/url from trajectory steps."""
    raw_steps = trajectory.get("steps", [])
    if not isinstance(raw_steps, list):
        return []
    result: list[dict[str, object]] = []
    for raw_step in raw_steps:
        step = _validate_step(raw_step)
        if step is None:
            continue
        url = step.get("active_url", "")
        for call in step["program"]["calls"]:
            name = call["name"]
            if name in ("waitForPageToSettle", "takeObservation"):
                continue
            detail = _summarize_call(name, call["kwargs"])
            result.append({"action": name, "detail": detail, "url": str(url)})
    return result


def _validate_step(raw: object) -> TrajectoryStep | None:
    """Validate a raw JSON value as a TrajectoryStep, returning None if malformed."""
    if not isinstance(raw, dict):
        return None
    program = raw.get("program")
    if not isinstance(program, dict):
        return None
    calls = program.get("calls")
    if not isinstance(calls, list):
        return None
    validated_calls: list[TrajectoryCall] = []
    for call in calls:
        if not isinstance(call, dict):
            continue
        name = call.get("name")
        kwargs = call.get("kwargs")
        if not isinstance(name, str) or not isinstance(kwargs, dict):
            continue
        validated_calls.append(TrajectoryCall(name=name, kwargs=kwargs))
    return TrajectoryStep(
        program=TrajectoryProgram(calls=validated_calls),
        active_url=str(raw.get("active_url", "")),
    )


def _summarize_call(name: str, kwargs: dict[str, object]) -> str:
    """Build a short human-readable detail string for a call."""
    if name == "think":
        return str(kwargs.get("text", ""))
    if name == "return":
        val = kwargs.get("value", "")
        return str(val)[:120]
    # For action calls, stringify kwargs compactly
    parts = [f"{k}={v}" for k, v in kwargs.items()]
    return ", ".join(parts)[:120] if parts else ""


def _compute_step_transitions(
    snapshots: list[list[SnapshotElement]],
) -> dict[int, dict[str, list[dict[str, object]]]]:
    """Diff consecutive snapshots, returning {step_number: structured_diff}."""
    from nova_act.cli.browser.services.browser_actions.utils import (
        generate_structured_transition,
    )

    transitions: dict[int, dict[str, list[dict[str, object]]]] = {}
    for i in range(1, len(snapshots)):
        diff = generate_structured_transition(snapshots[i - 1], snapshots[i])
        if diff["appeared"] or diff["removed"] or diff["changed"]:
            transitions[i + 1] = diff  # keyed by 1-based step number
    return transitions
