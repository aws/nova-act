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
"""Typed result dataclasses for BrowserActions methods."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import JsonValue


@dataclass
class NavigateResult:
    arrived: bool
    current_page: str
    attempts: int
    transition: str = ""


@dataclass
class ExploreResult:
    page_summary: str
    interactive_elements: list[str]
    current_state: str
    sections_explored: list[str]
    exploration_depth: int


@dataclass
class SearchResult:
    found: bool
    location: str
    summary: str
    transition: str = ""


@dataclass
class VerifyResult:
    passed: bool
    actual: str
    evidence: str
    transition: str = ""


@dataclass
class WaitForResult:
    met: bool
    elapsed_seconds: float
    polls: int
    transition: str = ""


@dataclass
class DiffResult:
    action: str
    observe: str
    before: JsonValue
    after: JsonValue


@dataclass
class FillFormResult:
    instruction: str
    submitted: bool
    outcome: str
    transition: str = ""


@dataclass
class AskResult:
    question: str
    answer: JsonValue
    url_changed: bool = False


@dataclass
class ExecuteResult:
    transition: str = ""


@dataclass
class ScrollToResult:
    reached: bool
    target: str
    attempts: int
    transition: str = ""


@dataclass
class ClickResult:
    clicked: str
    transition: str


@dataclass
class TypeResult:
    typed: str
    target: str
    transition: str = ""
