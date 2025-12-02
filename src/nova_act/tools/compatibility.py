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
"""Safeguards for tools provided to Act service + model."""

from typing import TYPE_CHECKING, Union, cast
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError
from strands.tools.mcp import MCPAgentTool
from strands.tools.mcp.mcp_types import MCPToolResult
from strands.types.tools import JSONSchema, ToolResult, ToolSpec
from typing_extensions import Self

from nova_act.types.act_errors import ActMCPError
from nova_act.types.errors import ValidationFailed
from nova_act.types.json_type import JSONType
from nova_act.util.logging import setup_logging

if TYPE_CHECKING:
    from nova_act.tools.actuator.interface.actuator import ActionType


_LOGGER = setup_logging(__name__)


TOOL_DESCRIPTION_MAX_LENGTH = 10000
TOOL_DESCRIPTION_MIN_LENGTH = 1
TOOL_NAME_MAX_LENGTH = 64
TOOL_NAME_MIN_LENGTH = 1
TOOL_NAME_PATTERN = "^[a-zA-Z0-9_-]+$"


def safe_mcp_tool_result_text(result: ToolResult) -> str | None:
    """Safely extract text from a strands ToolResult."""
    if "content" in result and not result["content"]:
        _LOGGER.debug(f"Unable to extract text from ToolResult with empty content: {result}")
        return None

    try:
        return result["content"][0]["text"]
    except Exception as e:  # pragma: no cover
        raise ActMCPError(f"Tool result does not conform to strands.types.tools.ToolResult contract: {result}") from e


def callable_tool(tool: Union["ActionType", MCPAgentTool]) -> "ActionType":
    """Abstraction around DecoratedFunctionTools and MCPAgentTools"""
    if isinstance(tool, MCPAgentTool):

        def mcp_tool(**kwargs: dict[str, JSONType]) -> JSONType:
            """Call an MCP tool and handle output."""
            # Call the tool
            mcp_tool_result: MCPToolResult = tool.mcp_client.call_tool_sync(
                tool_use_id=str(uuid4()),
                name=tool.tool_name,
                arguments=kwargs,
            )

            # Raise for error
            if mcp_tool_result["status"] == "error":
                raise ActMCPError(message=safe_mcp_tool_result_text(mcp_tool_result))

            # Return the result
            try:
                return cast(JSONType, mcp_tool_result["structuredContent"]["result"])
            except LookupError:  # pragma: no cover
                _LOGGER.warning(
                    f"MCP Tool '{tool.tool_name}' returned result without structured content. "
                    "Act will receive the response as plain text."
                )
                return safe_mcp_tool_result_text(mcp_tool_result)

        return cast("ActionType", mcp_tool)
    else:
        return tool


def safe_tool_spec(tool_spec: ToolSpec) -> ToolSpec:
    """Convenience wrapper for backwards-compatible ToolSpec."""
    try:
        return NovaToolSpec.from_strands(tool_spec).to_strands()
    except ValidationError as e:
        raise ValidationFailed(f"Received invalid ToolSpec from user-provided tool: {e.json()}") from e


class NovaToolSpec(BaseModel):
    """Backward-compatible ToolSpec.

    """

    name: str = Field(pattern=TOOL_NAME_PATTERN, min_length=TOOL_NAME_MIN_LENGTH, max_length=TOOL_NAME_MAX_LENGTH)
    """The unique name of the tool."""
    description: str = Field(min_length=TOOL_DESCRIPTION_MIN_LENGTH, max_length=TOOL_DESCRIPTION_MAX_LENGTH)
    """A human-readable description of what the tool does."""
    input_schema: JSONSchema[str, JSONType] = Field(alias="inputSchema")
    """JSON Schema defining the expected input parameters."""

    @classmethod
    def from_strands(cls, tool_spec: ToolSpec) -> Self:
        """Load from a Strands ToolSpec."""
        return cls(
            description=tool_spec["description"],
            inputSchema=tool_spec["inputSchema"],
            name=tool_spec["name"],
        )

    def to_strands(self) -> ToolSpec:
        """Dump to a Strands ToolSpec."""
        return cast(ToolSpec, self.model_dump(by_alias=True))
