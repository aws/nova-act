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
from typing import Any, Dict, TypedDict

"""
TypedDict definitions for Helios service API structures.

This module provides formal type definitions for all request and response
structures used in the Helios service integration, improving type safety
and code maintainability.
"""



# Base request structures
class ObservationDict(TypedDict):
    """Observation data structure containing browser state information."""

    activeURL: str


class PlanRequestDict(TypedDict):
    """Plan request structure sent to Helios service."""

    screenshotBase64: str
    observation: ObservationDict
    agentRunCreate: Dict[str, Any] | None


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
class PlanResponseDict(TypedDict):
    """Plan response structure from Helios service."""

    program: dict
    rawProgramBody: str


class PlanOutputDict(TypedDict):
    """Container for plan response data."""

    planResponse: PlanResponseDict


# Trace structures
class TraceMetadataDict(TypedDict):
    """Metadata for trace information."""

    sessionId: str
    actId: str
    stepId: str
    stepCount: int
    startTime: str


class ScreenshotDict(TypedDict):
    """Screenshot data structure in trace."""

    source: str
    sourceType: str


class OrchestrationTraceInputDict(TypedDict):
    """Input data for orchestration trace."""

    screenshot: ScreenshotDict
    activeURL: str
    prompt: str


class OrchestrationTraceOutputDict(TypedDict):
    """Output data for orchestration trace."""

    rawResponse: str


class OrchestrationTraceDict(TypedDict):
    """Complete orchestration trace structure."""

    input: OrchestrationTraceInputDict
    output: OrchestrationTraceOutputDict


class ExternalTraceDict(TypedDict):
    """External trace structure."""

    metadata: TraceMetadataDict
    orchestrationTrace: OrchestrationTraceDict
    failureTrace: Dict[str, Any] | None


class TraceDict(TypedDict):
    """Complete trace structure with external wrapper."""

    external: ExternalTraceDict


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


# Step object structures (internal SDK format)
class StepInputMetadataDict(TypedDict):
    """Metadata for step input."""

    activeUrl: str  # Note: different casing from API


class StepInputDict(TypedDict):
    """Input data for step object."""

    screenshot: str
    prompt: str
    metadata: StepInputMetadataDict
    agentRunCreate: Dict[str, Any] | None


class StepOutputDict(TypedDict, total=False):
    """Output data for step object."""

    rawProgramBody: str
    trace: TraceDict | None


class StepObjectDict(TypedDict):
    """Complete step object structure used internally by SDK."""

    input: StepInputDict
    output: StepOutputDict
