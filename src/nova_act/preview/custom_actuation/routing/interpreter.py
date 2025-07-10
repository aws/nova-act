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
import re
from typing import List, Tuple

from nova_act.impl.protocol import NovaActClientErrors
from nova_act.preview.custom_actuation.interface.browser import BrowserActuatorBase
from nova_act.preview.custom_actuation.interface.types.agent_redirect_error import AgentRedirectError
from nova_act.preview.custom_actuation.interface.types.program_error_response import ProgramErrorResponse
from nova_act.types.errors import NovaActError

FUNCTION_PATTERN = re.compile(r"(\w+)\((.*)\);?")
ARGS_PATTERN = re.compile(r'"([^"]*)"')
RETURN_PATTERN = re.compile(r"return( )?(?P<value>.+)?;")


class AWLInterpreter:
    """
    Parse and actuate
    Returns True iff Agent is done, False otherwise
    """

    def __init__(self, actuator: BrowserActuatorBase):
        self.actuator = actuator

    def interpret(self, raw_program_body: str) -> tuple[bool, str | None, ProgramErrorResponse | None]:
        """# noqa: E501
        Example raw_program_body:
            "think("I am on the amazon homepage. My task is to search for coffee maker. I see a search field,
                but it is empty. I need to type 'coffee maker' into the search field.");
            agentType("coffee maker", "<box>10,382,48,1136</box>");"
        """
        program_parts = raw_program_body.strip().split("\n")

        maybe_action = program_parts[-1]
        if not maybe_action:
            raise NovaActError("No action found in the program body")

        # Handle return
        return_match = RETURN_PATTERN.match(maybe_action)
        if return_match:
            value = return_match.group("value")
            if value is not None:
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
            return True, self.actuator._return(value), None

        # Handle throw actions provided by the model
        if maybe_action.startswith("throw "):
            value = maybe_action[6:-1]
            self.actuator.throw_agent_error(value)
            error: ProgramErrorResponse = {
                "type": "NovaActService",
                "subErrorCode": "AGENT_ERROR",
                "error": value,
            }
            return True, "Error", error

        fn_name, args = self._parse_function_like_string(maybe_action)

        try:
            # agentClick("<box>10,994,48,1040</box>");
            if "agentClick" == fn_name:
                if len(args) < 1:
                    raise NovaActError("Invalid number of arguments: " + maybe_action)
                self.actuator.agent_click(box=args[0])

            elif "agentType" == fn_name:
                if len(args) < 2:
                    raise NovaActError("Invalid number of arguments: " + maybe_action)

                if len(args) == 3:
                    # agentType("socks", "<box>10,376,48,836</box>", "pressEnter");
                    self.actuator.agent_type(value=args[0], box=args[1], pressEnter=args[2] == "pressEnter")
                else:
                    # agentType("socks", "<box>10,376,48,836</box>");
                    self.actuator.agent_type(value=args[0], box=args[1])

            # agentScroll("down", "<box>0,0,812,1452</box>");
            elif "agentScroll" == fn_name:
                if len(args) != 2:
                    raise NovaActError("Invalid number of arguments: " + maybe_action)
                self.actuator.agent_scroll(direction=args[0], box=args[1])

            # goToUrl("google.com");
            elif "goToUrl" == fn_name:
                if len(args) != 1:
                    raise NovaActError("Invalid number of arguments: " + maybe_action)
                self.actuator.go_to_url(url=args[0])

            if len(program_parts) > 1:
                # think("I am on the amazon homepage. My task is to search for coffee maker. I see a search field,
                # but it is empty. I need to type 'coffee maker' into the search field.")
                maybe_thought = program_parts[-2]
                fn_name, args = self._parse_function_like_string(maybe_thought)
                if fn_name == "think":
                    self.actuator.think(value=args[0])

            return False, None, None
        except AgentRedirectError:
            raise
        except Exception as e:
            err: ProgramErrorResponse = {
                "type": "NovaActClient",
                "message": str(e),
                "code": NovaActClientErrors.ACTUATION_ERROR.value,
            }
            return False, "Error", err

    def _parse_function_like_string(self, function_like_string: str) -> Tuple[str, List[str]]:
        match = FUNCTION_PATTERN.match(function_like_string)

        if not match:
            raise NovaActError("Invalid action format: " + function_like_string)
        fn_name: str = match.group(1)

        args: List[str] = ARGS_PATTERN.findall(match.group(2))
        return fn_name, args
