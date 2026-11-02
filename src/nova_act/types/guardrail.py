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
"""Guardrail types for NovaAct."""

from enum import Enum, auto
from typing import Callable, NamedTuple


class GuardrailDecision(Enum):
    """Decision returned by state guardrail callback."""

    PASS = auto()
    BLOCK = auto()


class GuardrailStateType(Enum):
    """Whether the guardrail is being consulted about the current observed state or a pending action.

    OBSERVATION is the state the agent has already reached; PROPOSED_ACTION is a navigation that is
    about to happen and can still be prevented (e.g. a click- or redirect-triggered navigation).
    """

    OBSERVATION = auto()
    PROPOSED_ACTION = auto()


class GuardrailInputState(NamedTuple):
    """Input representing state of the agent on which to apply a guardrail policy."""

    browser_url: str
    state_type: GuardrailStateType = GuardrailStateType.OBSERVATION


GuardrailCallable = Callable[[GuardrailInputState], GuardrailDecision]
