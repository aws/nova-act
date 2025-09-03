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
from typing_extensions import Literal, NotRequired, TypedDict

from nova_act.types.api.trace import TraceDict

# REQUEST TYPES


class BrowserDimensions(TypedDict):
    windowWidth: int
    windowHeight: int
    scrollHeight: int
    scrollLeft: int
    scrollTop: int
    scrollWidth: int


class Bbox(TypedDict):
    width: float
    height: float
    x: float
    y: float


class Observation(TypedDict):
    """Observation of a current browser state."""

    activeURL: str
    browserDimensions: BrowserDimensions
    idToBboxMap: dict[int, Bbox]
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
    planningModelServerHost: str | None
    task: str | None


class StepRequest(TypedDict):
    """Request to the /step endpoint."""

    agentRunId: str
    idToBboxMap: dict[int, Bbox]
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

    program: Program
    rawProgramBody: str
    trace: NotRequired[TraceDict]
    requestId: NotRequired[str]


class ProgramErrorResponse(TypedDict):
    error: NotRequired[str]
    type: Literal["NovaActService", "NovaActClient"]
    subErrorCode: NotRequired[str]
    requestId: NotRequired[str]
    exception: NotRequired[Exception]
    code: NotRequired[str | int]
    message: NotRequired[str]


class StepObjectInputMetadata(TypedDict):
    """Metadata for step request input."""

    activeURL: str


class StepObjectInput(TypedDict):
    """Step request input information."""

    screenshot: str
    prompt: str
    metadata: StepObjectInputMetadata
    agentRunCreate: NotRequired[AgentRunCreate]


class StepObject(TypedDict):
    """Information on a /step request/response."""

    input: StepObjectInput
    output: StepObjectOutput
    server_time_s: NotRequired[float]


class ParsedStepResponse(TypedDict):
    """Parsed response from the /step endpoint.

    """

    error: NotRequired[ProgramErrorResponse]
    program_statements: NotRequired[list[Statement]]
    raw_program_body: NotRequired[str]
    step_object: NotRequired[StepObject]
