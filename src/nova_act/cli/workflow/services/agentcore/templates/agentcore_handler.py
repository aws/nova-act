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
AgentCore handler for Nova Act workflows.

This handler expects the following to be present in the deployment:
- A main workflow file specified by the entry_point parameter
- All required dependencies installed via requirements.txt
- Proper AWS credentials and permissions for the agent runtime
- The workflow function should accept a payload parameter and return results
"""

import importlib.util
import os
from typing import Any, Dict

from bedrock_agentcore import BedrockAgentCoreApp

app = BedrockAgentCoreApp()


@app.route("/ping")
def ping() -> Dict[str, str]:
    return {"status": "healthy"}


@app.entrypoint
def handler(payload: Dict[str, Any]) -> None:  # type: ignore
    """Main entrypoint for AgentCore Runtime."""
    # Extract and set environment variables from payload
    if "AC_HANDLER_ENV" in payload:
        env_vars = payload.pop("AC_HANDLER_ENV")
        if isinstance(env_vars, dict):
            os.environ.update(env_vars)

    entry_point = os.environ.get("ENTRY_POINT", "main.py")
    module_name = entry_point.replace(".py", "")

    spec = importlib.util.spec_from_file_location(module_name, entry_point)
    if spec is None:
        raise ImportError(f"Could not load spec for {entry_point}")

    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise ImportError(f"No loader available for {entry_point}")

    spec.loader.exec_module(module)

    module.main(payload)


if __name__ == "__main__":
    app.run()
