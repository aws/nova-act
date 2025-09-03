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
from typing import Literal

from typing_extensions import NotRequired, TypedDict

"""
Trace type definitions for Nova Act API.

"""


ErrorCode = Literal[
    "INVALID_INPUT",
    "MODEL_ERROR",
    "INTERNAL_ERROR",
    "GUARDRAILS_ERROR",
    "UNAUTHORIZED_ERROR",
    "TOO_MANY_REQUESTS",
    "DAILY_QUOTA_LIMIT_ERROR",
    "SESSION_EXPIRED_ERROR",
]


class FailureTrace(TypedDict):
    """Failure trace of the service."""

    type: ErrorCode
    message: str


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
    failureTrace: NotRequired[FailureTrace]


class TraceDict(TypedDict):
    """Complete trace structure with external wrapper."""

    external: ExternalTraceDict
