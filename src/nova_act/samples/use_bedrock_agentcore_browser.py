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
"""Use the Bedrock AgentCore browser to perform a task.

This example demonstrates how to use the Bedrock AgentCore browser to perform a task against a remote browser.

Usage:
python -m nova_act.samples.use_bedrock_agentcore_browser
"""

from bedrock_agentcore.tools.browser_client import browser_session

from nova_act.nova_act import NovaAct


def main() -> None:
    with browser_session(region="us-east-1") as browser_client:
        ws_url, headers = browser_client.generate_ws_headers()

        with NovaAct(
            cdp_endpoint_url=ws_url,
            cdp_headers=headers,
            starting_page="https://nova.amazon.com/act/gym/next-dot",
        ) as nova:
            result = nova.act_get("How many direct routes to exoplanets are available?")
            print(f"There are {result.response} available direct routes to exoplanets.")


if __name__ == "__main__":
    main()
