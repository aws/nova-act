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
from uuid import uuid4

import jsonschema
from typing_extensions import Any

from nova_act.impl.program.base import Call, Program
from nova_act.tools.actuator.interface.actuator import ActionType
from nova_act.types.api.step import Statement
from nova_act.types.errors import InterpreterError
from nova_act.types.json_type import JSONType
from nova_act.util.argument_preparation import prepare_kwargs_for_actuation_calls
from nova_act.util.decode_string import safe_string


class NovaActInterpreter:
    """
    Parse and actuate
    Returns True iff Agent is done, False otherwise
    """

    @staticmethod
    def interpret_ast(statements: list[Statement], tool_map: dict[str, ActionType]) -> Program:
        """Parse AST instead of raw string"""

        if not statements:
            raise ValueError(f"No action found in the program: {statements}")

        last_stmt = statements[-1]

        if not last_stmt:
            raise ValueError(f"Empty statement found: {last_stmt}")

        stmt_kind = last_stmt["kind"]

        calls: list[Call] = []

        if call := NovaActInterpreter._process_think_statements(statements):
            calls.append(call)

        # Handle return
        if stmt_kind == "Return":
            call, value = None, None
            if expr := last_stmt.get("expr"):
                return_text = expr["value"]

                if return_text is not None:
                    value = safe_string(return_text)

            call = call or Call(name="return", id="return", kwargs={"value": value})
            calls.append(call)

        # Handle throw
        elif stmt_kind == "ThrowStatement":
            error_msg = ""
            if "expr" in last_stmt and last_stmt["expr"]["kind"] == "NewExpression" and last_stmt["expr"]["args"]:
                error_msg = safe_string(last_stmt["expr"]["args"][0]["value"])

            call = NovaActInterpreter._validated_call(
                tool=tool_map["throw"], call_id="throw", kwargs={"value": error_msg}
            )
            calls.append(call)

        # Handle function calls
        elif stmt_kind == "ExprStmt" and last_stmt["expr"]["kind"] == "Call":
            expr = last_stmt["expr"]
            fn_name = expr["func"]["var"]
            call_args = expr["args"]
            args = [NovaActInterpreter._extract_arg_value(arg) for arg in call_args]
            kwargs: dict[str, JSONType]

            # Use shared argument preparation logic for standard actuation calls
            if fn_name in ["agentClick", "agentHover", "agentType", "agentScroll", "goToUrl", "wait"]:
                try:
                    kwargs = prepare_kwargs_for_actuation_calls(fn_name, args)
                    # All fn_names are built in actuation functions, so we use the names for call_ids below
                    call = NovaActInterpreter._validated_call(tool=tool_map[fn_name], call_id=fn_name, kwargs=kwargs)
                    calls.append(call)
                except ValueError as e:
                    raise InterpreterError(str(e))
            else:
                raise InterpreterError(f"Unknown function: {fn_name}")
        else:
            raise ValueError(f"Received unhandled statement type: {stmt_kind}")

        return Program(calls=calls)

    @staticmethod
    def _extract_arg_value(arg: Any) -> Any:  # type: ignore[explicit-any]
        """Safely extract argument value from AST node"""
        if isinstance(arg, dict):
            if arg.get("kind") == "ObjectExpression":
                return NovaActInterpreter._parse_object_expression(arg)
            elif (value := arg.get("value")) is not None:
                if arg.get("kind") == "Str" or isinstance(value, str):
                    result = safe_string(value)
                    return result
                elif arg.get("kind") == "Number":
                    return value
                else:
                    return value
        return str(arg)

    # Handle "pressEnter" sub program
    @staticmethod
    def _parse_object_expression(obj_expr: dict[str, Any]) -> dict[str, Any]:  # type: ignore[explicit-any]
        """Parse ObjectExpression into a dict"""
        if obj_expr["kind"] != "ObjectExpression":
            return {}

        result = {}
        for prop in obj_expr.get("props", []):
            if prop["kind"] == "PropertyAssignment":
                key = prop["prop"]
                value_node = prop["value"]
                if value_node["kind"] == "Bool":
                    result[key] = value_node["value"]
                elif value_node["kind"] == "Str":
                    result[key] = safe_string(value_node["value"])
                elif value_node["kind"] == "Number":
                    result[key] = value_node["value"]
                elif value_node["kind"] == "ObjectExpression":
                    result[key] = NovaActInterpreter._parse_object_expression(value_node)
        return result

    @staticmethod
    def _process_think_statements(statements: list[Statement]) -> Call | None:
        if len(statements) > 1:
            prev_stmt = statements[-2]
            if (
                prev_stmt["kind"] == "ExprStmt"
                and prev_stmt["expr"]["kind"] == "Call"
                and prev_stmt["expr"]["func"]["var"] == "think"
            ):
                think_value = safe_string(prev_stmt["expr"]["args"][0]["value"])
                return Call(name="think", id="think", kwargs={"value": think_value})

        return None

    @staticmethod
    def _validated_call(tool: ActionType, call_id: str, kwargs: dict[str, JSONType]) -> Call:
        try:
            jsonschema.validate(
                instance=kwargs,
                schema=tool.tool_spec["inputSchema"]["json"],
            )
        except jsonschema.exceptions.ValidationError as e:
            raise InterpreterError(f"Received invalid arguments for {tool.tool_name}: {str(e)}")

        return Call(name=tool.tool_name, id=call_id, kwargs=kwargs)
