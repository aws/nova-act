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

from typing_extensions import Any, NotRequired, TypedDict

from nova_act.impl.actuation.interface.browser import BrowserActuatorBase
from nova_act.impl.actuation.interface.types.agent_redirect_error import (
    AgentRedirectError,
)
from nova_act.impl.protocol import NovaActClientErrors
from nova_act.types.api.step import ProgramErrorResponse, Statement
from nova_act.types.errors import InterpreterError
from nova_act.types.events import EventType, LogType
from nova_act.util.event_handler import EventHandler



class InterpretedAst(TypedDict):
    """Result from an interpreted AST."""

    is_act_done: bool
    result: str | None
    program_error: NotRequired[ProgramErrorResponse]


class NovaActInterpreter:
    """
    Parse and actuate
    Returns True iff Agent is done, False otherwise
    """

    def __init__(self, actuator: BrowserActuatorBase, event_handler: EventHandler):
        self.actuator = actuator
        self._event_handler = event_handler

    def _decode_string(self, value: Any) -> str:
        """Helper to decode unicode strings"""
        return codecs.decode(value, "unicode_escape") if isinstance(value, str) else value

    def interpret_ast(self, statements: list[Statement]) -> InterpretedAst:
        """Parse AST instead of raw string"""

        if not statements:
            return InterpretedAst(
                is_act_done=True,
                result=None,
                program_error=ProgramErrorResponse(
                    type="NovaActClient",
                    code=NovaActClientErrors.BAD_RESPONSE.value,
                    message=f"No action found in the program: {statements}",
                ),
            )

        last_stmt = statements[-1]

        if not last_stmt:
            return InterpretedAst(
                is_act_done=True,
                result=None,
                program_error=ProgramErrorResponse(
                    type="NovaActClient",
                    code=NovaActClientErrors.BAD_RESPONSE.value,
                    message=f"Empty statement found: {statements}",
                ),
            )

        stmt_kind = last_stmt["kind"]

        # Handle return
        if stmt_kind == "Return":
            value = None
            if expr := last_stmt.get("expr"):
                value = self._decode_string(expr["value"])
            self._process_think_statements(statements)
            self._event_handler.send_event(type=EventType.ACTION, action="return", data=value)
            result = self.actuator._return(value)
            return InterpretedAst(is_act_done=True, result=str(result) if result is not None else result)

        # Handle throw
        if stmt_kind == "ThrowStatement":
            error_msg = ""
            if "expr" in last_stmt and last_stmt["expr"]["kind"] == "NewExpression" and last_stmt["expr"]["args"]:
                error_msg = self._decode_string(last_stmt["expr"]["args"][0]["value"])
            error: ProgramErrorResponse = {
                "type": "NovaActService",
                "subErrorCode": "AGENT_ERROR",
                "error": str(self.actuator.throw_agent_error(error_msg)),
            }
            self._process_think_statements(statements)
            self._event_handler.send_event(type=EventType.ACTION, action="throw", data=error_msg)
            return InterpretedAst(is_act_done=True, result="Error", program_error=error)

        # Handle function calls
        if stmt_kind == "ExprStmt" and last_stmt["expr"]["kind"] == "Call":
            call = last_stmt["expr"]
            fn_name = call["func"]["var"]
            call_args = call["args"]
            args = [self._extract_arg_value(arg) for arg in call_args]

            try:
                # Process and send think statement
                self._process_think_statements(statements)
                # Process and send action
                self._event_handler.send_event(type=EventType.ACTION, action=fn_name, data=args)

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
                    seconds = float(args[0]) if args else 0.0
                    self.actuator.wait(seconds)
                else:
                    raise InterpreterError(f"Unknown function: {fn_name}")
                return InterpretedAst(is_act_done=False, result=None)

            except AgentRedirectError:
                raise
            except InterpreterError as e:
                err: ProgramErrorResponse = {
                    "type": "NovaActClient",
                    "message": str(e),
                    "code": NovaActClientErrors.INTERPRETATION_ERROR.value,
                }
                self._event_handler.send_event(type=EventType.LOG, log_level=LogType.ERROR, data=err)
                return InterpretedAst(is_act_done=True, result="Error", program_error=err)
            except Exception as e:
                err = {
                    "type": "NovaActClient",
                    "message": str(e),
                    "exception": e,
                    "code": NovaActClientErrors.ACTUATION_ERROR.value,
                }
                self._event_handler.send_event(type=EventType.LOG, log_level=LogType.ERROR, data=err)
                return InterpretedAst(is_act_done=False, result="Error", program_error=err)

        return InterpretedAst(
            is_act_done=True,
            result=None,
            program_error=ProgramErrorResponse(
                type="NovaActClient",
                code=NovaActClientErrors.BAD_RESPONSE.value,
                message=f"Unhandled statement type: {stmt_kind}",
            ),
        )

    def _extract_arg_value(self, arg: Any) -> Any:
        """Safely extract argument value from AST node"""
        if isinstance(arg, dict) and (value := arg.get("value")) is not None:
            if arg.get("kind") == "Str":
                return self._decode_string(value)
            elif arg.get("kind") == "Number":
                return value
            else:
                return value
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

    def _process_think_statements(self, statements: list[Statement]) -> None:
        if len(statements) > 1:
            prev_stmt = statements[-2]
            if (
                prev_stmt["kind"] == "ExprStmt"
                and prev_stmt["expr"]["kind"] == "Call"
                and prev_stmt["expr"]["func"]["var"] == "think"
            ):
                think_value = self._decode_string(prev_stmt["expr"]["args"][0]["value"])
                self._event_handler.send_event(type=EventType.ACTION, action="think", data=think_value)
                self.actuator.think(value=think_value)
