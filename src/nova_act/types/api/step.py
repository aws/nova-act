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
from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import NotRequired, TypedDict

from nova_act.types.api.trace import TraceDict

# REQUEST TYPES


class BrowserDimensions(TypedDict):
    windowWidth: int
    windowHeight: int
    scrollHeight: int
    scrollLeft: int
    scrollTop: int
    scrollWidth: int


@dataclass(frozen=True)
class BboxTLBR:
    top: float
    left: float
    bottom: float
    right: float

    def __post_init__(self) -> None:
        for field in ("top", "left", "bottom", "right"):
            value = getattr(self, field)
            if value < 0:
                raise ValueError(f"{field} ({value}) must be >= 0")
        if self.top >= self.bottom:
            raise ValueError(f"top ({self.top}) must be less than bottom ({self.bottom})")
        if self.left >= self.right:
            raise ValueError(f"left ({self.left}) must be less than right ({self.right})")

    def validate_in_viewport(self, *, height: int, width: int) -> None:
        if self.bottom > height:
            raise ValueError(f"bottom ({self.bottom}) below viewport ({height})")
        if self.right > width:
            raise ValueError(f"right ({self.right}) to the right of viewport ({width})")

    def iou(self, other: BboxTLBR) -> float:
        # Determine intersection bounds
        inter_top = max(self.top, other.top)
        inter_left = max(self.left, other.left)
        inter_bottom = min(self.bottom, other.bottom)
        inter_right = min(self.right, other.right)

        # Compute intersection area
        inter_width = max(0.0, inter_right - inter_left)
        inter_height = max(0.0, inter_bottom - inter_top)
        inter_area = inter_width * inter_height

        # Compute individual areas
        area1 = max(0.0, (self.right - self.left)) * max(0.0, (self.bottom - self.top))
        area2 = max(0.0, (other.right - other.left)) * max(0.0, (other.bottom - other.top))

        # Compute union area
        union_area = area1 + area2 - inter_area

        if union_area == 0.0:
            return 0.0

        return inter_area / union_area


class BboxTLWH(TypedDict):
    width: float
    height: float
    x: float
    y: float


class Observation(TypedDict):
    """Observation of a current browser state."""

    activeURL: str
    browserDimensions: BrowserDimensions
    idToBboxMap: dict[int, BboxTLWH]
    simplifiedDOM: str
    timestamp_ms: int
    userAgent: str


class PlannerFunctionArgs(TypedDict):
    """Arguments to the planner function."""

    task: str | None


class AgentRunCreate(TypedDict):
    """Configuration to create an Agent run."""

    agentConfigName: str
    id: str
    plannerFunctionArgs: PlannerFunctionArgs
    plannerFunctionName: str
    task: str | None


class StepPlanRequest(TypedDict):
    """Plan Request to the /step endpoint."""

    agentRunId: str
    idToBboxMap: dict[int, BboxTLWH]
    observation: Observation
    screenshotBase64: str
    tempReturnPlanResponse: bool
    errorExecutingPreviousStep: NotRequired[str]
    agentRunCreate: NotRequired[AgentRunCreate]


# RESPONSE TYPES


class Function(TypedDict):
    """Function invoked in a given Expression."""

    var: str


class Expression(TypedDict):
    """Expression within a given statement."""

    value: NotRequired[str | None]
    kind: NotRequired[str]
    func: NotRequired[Function]
    args: NotRequired[list]  # type: ignore[type-arg]


class Statement(TypedDict):
    """Statement within a given program."""

    kind: str
    expr: NotRequired[Expression]


class ProgramBodyContent(TypedDict):
    """Inner content containing the actual statements."""

    body: list[Statement]


class ProgramBodyWrapper(TypedDict):
    """Middle wrapper in the program structure."""

    body: ProgramBodyContent


class Program(TypedDict):
    """Program structure as returned by API."""

    body: list[ProgramBodyWrapper]


class PlanResponse(TypedDict):
    """Plan response structure."""

    program: Program
    rawProgramBody: str


class StepObjectOutput(TypedDict):
    """Output structure for StepObject."""

    program: list[Statement]
    rawProgramBody: str
    trace: NotRequired[TraceDict]
    requestId: NotRequired[str]


class StepObjectInputMetadata(TypedDict):
    """Metadata for step request input."""

    activeURL: str


class StepObjectInput(TypedDict):
    """Step request input information."""

    screenshot: str
    prompt: str
    metadata: StepObjectInputMetadata
    agentRunCreate: NotRequired[AgentRunCreate]
