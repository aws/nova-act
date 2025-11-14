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
"""
Shared utility functions for preparing arguments for actuation calls.
"""

from typing import Dict, List

from nova_act.types.json_type import JSONType


def prepare_kwargs_for_actuation_calls(tool_name: str, args: List[JSONType]) -> Dict[str, JSONType]:
    """
    Prepare kwargs for actuation calls based on tool name and arguments.

    Args:
        tool_name: Name of the tool/function being called
        args: List of arguments to convert to kwargs

    Returns:
        Dictionary of keyword arguments

    Raises:
        ValueError: If invalid number of arguments or invalid argument types
    """
    match tool_name:
        case "agentClick":
            if len(args) < 1:
                raise ValueError(f"Invalid number of arguments for '{tool_name}': expected 1, got 0")
            kwargs = {"box": args[0]}
            if len(args) > 1:
                if isinstance(args[1], dict):
                    # Handle options object format
                    if click_type := args[1].get("clickType"):
                        kwargs["click_type"] = click_type
                else:
                    # Handle direct click_type argument
                    kwargs["click_type"] = args[1]
            return kwargs

        case "agentHover":
            if len(args) != 1:
                raise ValueError(f"Invalid number of arguments for '{tool_name}': expected 1, got {len(args)}")
            kwargs = {"box": args[0]}
            return kwargs

        case "agentScroll":
            if len(args) != 2:
                raise ValueError(f"Invalid number of arguments for '{tool_name}': expected 2, got {len(args)}")
            kwargs = {"direction": args[0], "box": args[1]}
            return kwargs

        case "agentType":
            if len(args) < 2:
                raise ValueError(f"Invalid number of arguments for '{tool_name}': expected 2, got {len(args)}")
            kwargs = {"value": args[0], "box": args[1], "pressEnter": False}
            if len(args) > 2:
                if isinstance(args[2], dict):
                    # Handle options object format
                    kwargs["pressEnter"] = args[2].get("pressEnter", False)
                else:
                    # Handle direct pressEnter argument
                    kwargs["pressEnter"] = args[2]
            return kwargs

        case "goToUrl":
            if len(args) < 1:
                raise ValueError(f"Invalid number of arguments for '{tool_name}': expected 1, got 0")
            kwargs = {"url": args[0]}
            return kwargs

        case "return":
            if len(args) == 1:
                return {"value": args[0]}
            else:
                return {"value": ""}

        case "takeObservation":
            return {}

        case "think":
            if len(args) < 1:
                raise ValueError(f"Invalid number of arguments for '{tool_name}': expected 1, got 0")
            return {"value": args[0]}

        case "throwAgentError" | "throw":
            if len(args) < 1:
                raise ValueError(f"Invalid number of arguments for '{tool_name}': expected 1, got 0")
            return {"value": args[0]}

        case "wait":
            if len(args) < 1:
                raise ValueError(f"Invalid number of arguments for '{tool_name}': expected 1, got 0")
            if isinstance(args[0], (int, float)):
                return {"seconds": float(args[0])}
            if isinstance(args[0], str):
                return {"seconds": float(args[0])}
            raise ValueError(f"Invalid type: {type(args[0])} and value: {args[0]} for 'wait'.")

        case "waitForPageToSettle":
            return {}

    raise ValueError(f"Received unexpected input args: {args} for tool name: {tool_name}")
