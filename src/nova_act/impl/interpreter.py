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
import json

from typing_extensions import Any

from nova_act.impl.program import Call, Program
from nova_act.types.api.step import Statement
from nova_act.types.errors import InterpreterError
from nova_act.util.decode_string import decode_string


class NovaActInterpreter:
    """
    Parse and actuate
    Returns True iff Agent is done, False otherwise
    """


    def interpret_ast(self, statements: list[Statement]) -> Program:
        """Parse AST instead of raw string"""

        if not statements:
            raise ValueError(f"No action found in the program: {statements}")

        last_stmt = statements[-1]

        if not last_stmt:
            raise ValueError(f"Empty statement found: {last_stmt}")

        stmt_kind = last_stmt["kind"]

        calls: list[Call] = []

        if call := self._process_think_statements(statements):
            calls.append(call)

        # Handle return
        if stmt_kind == "Return":
            call, value = None, None
            if expr := last_stmt.get("expr"):
                return_text = expr["value"]
                if return_text is not None:
                    value = decode_string(return_text)

            call = call or Call(name="return", kwargs={"value": value})
            calls.append(call)

        # Handle throw
        elif stmt_kind == "ThrowStatement":
            error_msg = ""
            if "expr" in last_stmt and last_stmt["expr"]["kind"] == "NewExpression" and last_stmt["expr"]["args"]:
                error_msg = decode_string(last_stmt["expr"]["args"][0]["value"])

            call = Call(name="throw", kwargs={"value": error_msg})
            calls.append(call)

        # Handle function calls
        elif stmt_kind == "ExprStmt" and last_stmt["expr"]["kind"] == "Call":
            expr = last_stmt["expr"]
            fn_name = expr["func"]["var"]
            call_args = expr["args"]
            args = [self._extract_arg_value(arg) for arg in call_args]

            if fn_name == "agentClick":
                if len(args) < 1:
                    raise InterpreterError(f"Invalid number of arguments for {fn_name}: expected 1, got {len(args)}")

                kwargs = {"box": args[0]}
                if len(args) > 1 and isinstance(args[1], dict):
                    if click_type := args[1].get("clickType"):
                        kwargs["click_type"] = click_type

                call = Call(name="agentClick", kwargs=kwargs)
                calls.append(call)
            elif fn_name == "agentType":
                if len(args) < 2:
                    raise InterpreterError(f"Invalid number of arguments for {fn_name}: expected 2-3, got {len(args)}")

                # Check for options object
                press_enter = False
                if len(args) == 3 and isinstance(args[2], dict):
                    press_enter = args[2].get("pressEnter", False)

                kwargs = {"value": args[0], "box": args[1], "pressEnter": press_enter}
                call = Call(name="agentType", kwargs=kwargs)
                calls.append(call)
            elif fn_name == "agentScroll":
                if len(args) != 2:
                    raise InterpreterError(f"Invalid number of arguments for {fn_name}: expected 2, got {len(args)}")
                kwargs = {"direction": args[0], "box": args[1]}
                call = Call(name="agentScroll", kwargs=kwargs)
                calls.append(call)
            elif fn_name == "goToUrl":
                if len(args) != 1:
                    raise InterpreterError(f"Invalid number of arguments for {fn_name}: expected 1, got {len(args)}")
                kwargs = {"url": args[0]}
                call = Call(name="goToUrl", kwargs=kwargs)
                calls.append(call)
            elif fn_name == "wait":
                seconds = float(args[0]) if args else 0.0
                kwargs = {"seconds": seconds}
                call = Call(name="wait", kwargs=kwargs)
                calls.append(call)
            else:
                raise InterpreterError(f"Unknown function: {fn_name}")
        else:
            raise ValueError(f"Received unhandled statement type: {stmt_kind}")

        return Program(calls)

    def _extract_arg_value(self, arg: Any) -> Any:  # type: ignore[explicit-any]
        """Safely extract argument value from AST node"""
        if isinstance(arg, dict):
            if arg.get("kind") == "ObjectExpression":
                return self._parse_object_expression(arg)
            elif (value := arg.get("value")) is not None:
                if arg.get("kind") == "Str" or isinstance(value, str):
                    result = decode_string(value)
                    return result
                elif arg.get("kind") == "Number":
                    return value
                else:
                    return value
        return str(arg)

    # Handle "pressEnter" sub program
    def _parse_object_expression(self, obj_expr: dict[str, Any]) -> dict[str, Any]:  # type: ignore[explicit-any]
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
                    result[key] = decode_string(value_node["value"])
                elif value_node["kind"] == "Number":
                    result[key] = value_node["value"]
        return result

    def _process_think_statements(self, statements: list[Statement]) -> Call | None:
        if len(statements) > 1:
            prev_stmt = statements[-2]
            if (
                prev_stmt["kind"] == "ExprStmt"
                and prev_stmt["expr"]["kind"] == "Call"
                and prev_stmt["expr"]["func"]["var"] == "think"
            ):
                think_value = decode_string(prev_stmt["expr"]["args"][0]["value"])
                return Call(name="think", kwargs={"value": think_value})

        return None
