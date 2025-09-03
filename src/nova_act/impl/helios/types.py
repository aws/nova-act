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
from typing_extensions import TypedDict

from nova_act.types.api.step import (
    AgentRunCreate,
    Observation,
    PlanResponse,
)
from nova_act.types.api.trace import TraceDict

"""
TypedDict definitions for Helios service API structures.

This module provides formal type definitions for all request and response
structures used in the Helios service integration.
"""



class PlanRequestDict(TypedDict):
    """Plan request structure sent to Helios service."""

    screenshotBase64: str
    observation: Observation
    agentRunCreate: AgentRunCreate | None


class PlanInputDict(TypedDict):
    """Container for plan request data."""

    planRequest: PlanRequestDict


class HeliosRequestDict(TypedDict):
    """Complete request structure for Helios service."""

    enableTrace: bool
    nexusActId: str
    nexusSessionId: str
    planInput: PlanInputDict


# Base response structures
class PlanOutputDict(TypedDict):
    """Container for plan response data."""

    planResponse: PlanResponse


class HeliosResponseDict(TypedDict):
    """Complete response structure from Helios service."""

    planOutput: PlanOutputDict
    trace: TraceDict | None


# Error response structures
class HeliosErrorDict(TypedDict):
    """Error structure from Helios service."""

    code: str  # String enum: INVALID_INPUT, MODEL_ERROR, etc.
    message: str


class HeliosErrorResponseDict(TypedDict):
    """Complete error response structure from Helios service."""

    planOutput: None  # Always null when error is present
    error: HeliosErrorDict
