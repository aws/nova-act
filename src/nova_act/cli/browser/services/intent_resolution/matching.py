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
"""3-tier matching: format detection, exact match, token set ratio."""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from nova_act.cli.browser.services.intent_resolution.snapshot import SnapshotElement

# Tier 1 patterns — require unambiguous CSS syntax signals (structural heuristic).
# Bare HTML tag names ("button", "search", "menu") are NOT matched — they fall through
# to Tier 2/3 name matching, which is strictly better for single-word inputs.
_CSS_SELECTOR_RE = re.compile(r"^[#.\[]|^[a-z]+[\[.#:]", re.IGNORECASE)
_SNAPSHOT_REF_RE = re.compile(r"^e\d+$", re.IGNORECASE)

FUZZY_SCORE_THRESHOLD = 85
FUZZY_GAP_THRESHOLD = 15


@dataclass
class FormatMatch:
    """Result of Tier 1 format detection."""

    kind: str  # "css_selector" or "snapshot_ref"
    value: str


@dataclass
class MatchResult:
    """Result of Tier 3 token set ratio matching."""

    element: SnapshotElement | None
    score: float
    confident: bool


def detect_format(target: str) -> FormatMatch | None:
    """Tier 1: Detect if target is a CSS selector or snapshot ref."""
    target = target.strip()
    if _SNAPSHOT_REF_RE.match(target):
        return FormatMatch(kind="snapshot_ref", value=target)
    if _CSS_SELECTOR_RE.match(target):
        return FormatMatch(kind="css_selector", value=target)
    return None


def exact_match(target: str, elements: list[SnapshotElement]) -> SnapshotElement | None:
    """Tier 2: Case-insensitive exact name match. Returns None if 0 or 2+ matches."""
    target_lower = target.strip().lower()
    matches = [e for e in elements if e.name and e.name.lower() == target_lower]
    return matches[0] if len(matches) == 1 else None


def token_set_match(target: str, elements: list[SnapshotElement]) -> MatchResult:
    """Tier 3: Fuzzy match via rapidfuzz token_set_ratio.

    Confident if best score >= FUZZY_SCORE_THRESHOLD AND gap to second-best >= FUZZY_GAP_THRESHOLD.
    """
    named = [e for e in elements if e.name]
    if not named:
        return MatchResult(element=None, score=0.0, confident=False)

    scored = [(e, fuzz.token_set_ratio(target, e.name)) for e in named]
    scored.sort(key=lambda x: x[1], reverse=True)

    best_elem, best_score = scored[0]
    second_score = scored[1][1] if len(scored) > 1 else 0.0
    gap = best_score - second_score

    if best_score >= FUZZY_SCORE_THRESHOLD and gap >= FUZZY_GAP_THRESHOLD:
        return MatchResult(element=best_elem, score=best_score, confident=True)

    return MatchResult(
        element=best_elem if best_score >= FUZZY_SCORE_THRESHOLD else None, score=best_score, confident=False
    )
