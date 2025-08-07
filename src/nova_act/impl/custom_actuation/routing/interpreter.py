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
import codecs
from typing import Any

from nova_act.impl.custom_actuation.interface.browser import BrowserActuatorBase
from nova_act.impl.custom_actuation.interface.types.agent_redirect_error import AgentRedirectError
from nova_act.impl.custom_actuation.interface.types.program_error_response import ProgramErrorResponse
from nova_act.impl.protocol import NovaActClientErrors
from nova_act.types.errors import InterpreterError


class NovaActInterpreter:
    """
    Parse and actuate
    Returns True iff Agent is done, False otherwise
    """

    def __init__(self, actuator: BrowserActuatorBase):
        self.actuator = actuator

    def _decode_string(self, value: Any) -> str:
        """Helper to decode unicode strings"""
        return codecs.decode(value, "unicode_escape") if isinstance(value, str) else value

    def interpret_ast(self, program_ast: dict) -> tuple[bool, str | None, ProgramErrorResponse | None]:
        """Parse AST instead of raw string"""
        statements = self._extract_statements(program_ast)

        if not statements:
            raise InterpreterError("No action found in the program")

        last_stmt = statements[-1]

        if not last_stmt:
            raise InterpreterError("Empty statement found")

        stmt_kind = last_stmt["kind"]

        # Handle return
        if stmt_kind == "Return":
            value = None
            if expr := last_stmt.get("expr"):
                value = self._decode_string(expr["value"])
            return True, self.actuator._return(value), None

        # Handle throw
        if stmt_kind == "ThrowStatement":
            error_msg = ""
            if "expr" in last_stmt and last_stmt["expr"]["kind"] == "NewExpression" and last_stmt["expr"]["args"]:
                error_msg = self._decode_string(last_stmt["expr"]["args"][0]["value"])

            self.actuator.throw_agent_error(error_msg)
            error: ProgramErrorResponse = {
                "type": "NovaActService",
                "subErrorCode": "AGENT_ERROR",
                "error": error_msg,
            }
            return True, "Error", error

        # Handle function calls
        if stmt_kind == "ExprStmt" and last_stmt["expr"]["kind"] == "Call":
            call = last_stmt["expr"]
            fn_name = call["func"]["var"]
            call_args = call["args"]
            args = [self._extract_arg_value(arg) for arg in call_args]

            try:
                if fn_name == "agentClick":
                    if len(args) < 1:
                        raise InterpreterError(
                            f"Invalid number of arguments for {fn_name}: expected 1, got {len(args)}"
                        )
                    self.actuator.agent_click(box=args[0])
                elif fn_name == "agentType":
                    if len(call_args) < 2:
                        raise InterpreterError(
                            f"Invalid number of arguments for {fn_name}: expected 2-3, got {len(call_args)}"
                        )

                    value = self._extract_arg_value(call_args[0])
                    box = self._extract_arg_value(call_args[1])

                    # Check for options object
                    press_enter = False
                    if len(call_args) == 3:
                        third_arg = call_args[2]
                        if third_arg["kind"] == "ObjectExpression":
                            options = self._parse_object_expression(third_arg)
                            press_enter = options.get("pressEnter", False)

                    self.actuator.agent_type(value=value, box=box, pressEnter=press_enter)
                elif fn_name == "agentScroll":
                    if len(args) != 2:
                        raise InterpreterError(
                            f"Invalid number of arguments for {fn_name}: expected 2, got {len(args)}"
                        )
                    self.actuator.agent_scroll(direction=args[0], box=args[1])
                elif fn_name == "goToUrl":
                    if len(args) != 1:
                        raise InterpreterError(
                            f"Invalid number of arguments for {fn_name}: expected 1, got {len(args)}"
                        )
                    self.actuator.go_to_url(url=args[0])
                elif fn_name == "wait":
                    self.actuator.wait_for_page_to_settle()
                else:
                    raise InterpreterError(f"Unknown function: {fn_name}")

                # Handle think from previous statement
                if len(statements) <= 1:
                    return False, None, None

                prev_stmt = statements[-2]
                if (
                    prev_stmt["kind"] == "ExprStmt"
                    and prev_stmt["expr"]["kind"] == "Call"
                    and prev_stmt["expr"]["func"]["var"] == "think"
                ):
                    think_value = self._decode_string(prev_stmt["expr"]["args"][0]["value"])
                    self.actuator.think(value=think_value)

                return False, None, None

            except AgentRedirectError:
                raise
            except InterpreterError as e:
                err: ProgramErrorResponse = {
                    "type": "NovaActClient",
                    "message": str(e),
                    "code": NovaActClientErrors.INTERPRETATION_ERROR.value,
                }
                return True, "Error", err
            except Exception as e:
                err = {
                    "type": "NovaActClient",
                    "message": str(e),
                    "code": NovaActClientErrors.ACTUATION_ERROR.value,
                }
                return False, "Error", err

        raise InterpreterError(f"Unhandled statement type: {stmt_kind}")

    def _extract_statements(self, program_ast: dict) -> list:
        """Extract statements from AST"""
        return program_ast["body"][0]["body"]["body"]

    def _extract_arg_value(self, arg: Any) -> str:
        """Safely extract argument value from AST node"""
        if isinstance(arg, dict) and (value := arg.get("value")) is not None:
            return self._decode_string(value)
        return str(arg)

    # Handle "pressEnter" sub program
    def _parse_object_expression(self, obj_expr: dict[str, Any]) -> dict[str, Any]:
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
                    result[key] = self._decode_string(value_node["value"])
                elif value_node["kind"] == "Number":
                    result[key] = value_node["value"]
        return result
