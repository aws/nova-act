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
"""Intent resolution module — routes agent intent to fast (Playwright) or smart (AI) path."""

from nova_act.cli.browser.services.intent_resolution.matching import (
    FormatMatch,
    MatchResult,
    detect_format,
    exact_match,
    token_set_match,
)
from nova_act.cli.browser.services.intent_resolution.resolver import (
    ResolutionPath,
    ResolvedTarget,
    resolve,
)
from nova_act.cli.browser.services.intent_resolution.snapshot import (
    SnapshotElement,
    flatten_snapshot,
)

__all__ = [
    "FormatMatch",
    "MatchResult",
    "ResolvedTarget",
    "ResolutionPath",
    "SnapshotElement",
    "detect_format",
    "exact_match",
    "flatten_snapshot",
    "resolve",
    "token_set_match",
]
