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
"""Error message constants for NovaAct SDK.

This module contains reusable error messages displayed to users when specific
conditions are encountered. Messages are formatted as boxed warnings for better visibility.

"""

from nova_act.util.constants import NOVA_ACT_AWS_SERVICE, NOVA_ACT_FREE_VERSION
from nova_act.util.logging import create_warning_box


def get_api_key_error_message_for_workflow() -> str:
    """Get the error message for ambiguous authentication when API key is found in environment.

    Returns:
        A formatted error message string.
    """
    return create_warning_box(
        [
            "Ambiguous Authentication Failure",
            "Found API Key environment variable (NOVA_ACT_API_KEY) while using Workflow context.",
            "",
            f"To use {NOVA_ACT_FREE_VERSION}: set the API key explicitly using",
            '  Workflow(api_key="<YOUR KEY HERE>", ...) or @workflow(api_key="<YOUR KEY HERE>", ...)',
            "",
            f"To use {NOVA_ACT_AWS_SERVICE}: unset the API key environment variable:",
            "  unset NOVA_ACT_API_KEY",
        ]
    )


def get_no_authentication_error() -> str:
    """Get the error message when no authentication credentials are found.

    Returns:
        A formatted error message string.
    """
    return create_warning_box(
        [
            "Authentication Failed",
            "",
            "The NovaAct SDK supports two forms of authentication:",
            f"1. API Key for {NOVA_ACT_FREE_VERSION}, which can be obtained at",
            "   https://nova.amazon.com/act",
            f"2. AWS Authentication for {NOVA_ACT_AWS_SERVICE}, which uses standard",
            "   boto Session credentials",
            "",
            "Please configure one or the other in order to run your workflow.",
        ]
    )


def get_missing_workflow_definition_error() -> str:
    """Get the error message when AWS credentials are set but NOVA_ACT_API_KEY is not and
    user is trying to run a non-workflow example.

    Returns:
        A formatted error message string.
    """
    return create_warning_box(
        [
            "Authentication Failed With Invalid Credentials Configuration",
            "",
            "There are two options for authenticating with Nova Act:",
            f"(1) {NOVA_ACT_FREE_VERSION} with API keys or (2) {NOVA_ACT_AWS_SERVICE} with AWS credentials.",
            "",
            f"To use (1) {NOVA_ACT_FREE_VERSION}, set the NOVA_ACT_API_KEY environment variable",
            'or pass in explicitly using NovaAct(nova_act_api_key="<YOUR KEY HERE>", ...)',
            "To generate an API Key go to https://nova.amazon.com/act?tab=dev_tools",
            "",
            f"To use (2) {NOVA_ACT_AWS_SERVICE}, you must use a Workflow construct. For example:",
            "",
            '@workflow(workflow_definition_name="<your-workflow-name>", model_id="nova-act-latest")',
            "def explore_destinations():",
            '    with NovaAct(starting_page="https://nova.amazon.com/act/gym/next-dot/search") as nova:',
            '        nova.act("Find flights from Boston to Wolf on Feb 22nd")',
            "",
            "To create a workflow definition name, use the Nova Act CLI or go to",
            "https://docs.aws.amazon.com/nova-act/latest/userguide/step-2-develop-locally.html#develop-with-aws-iam",
            "",
            "Please configure one or the other in order to run your workflow.",
        ]
    )
