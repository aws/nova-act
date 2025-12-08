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
"""Log into email app, and print the title of first email if approved.

Shows how to use Nova Act to provide HITL (Human in the loop) callbacks
to let human takeover the UI, and approve a workflow step.

Usage:
python -m nova_act.samples.print_number_of_emails --email_app_url <email_service_url>
"""

import fire  # type: ignore

from nova_act import NovaAct
from nova_act.tools.human.interface.human_input_callback import (
    ApprovalResponse,
    HumanInputCallbacksBase,
    UiTakeoverResponse,
)


class ConsoleBasedHumanInputCallbacks(HumanInputCallbacksBase):
    def approve(self, message: str) -> ApprovalResponse:
        print(f"\n🤖 Approval required for act_id: {self.current_act_id} inside act_session_id: {self.act_session_id}:")
        print(f"   {message}")

        while True:
            answer = input("   Please enter '(y)es' or '(n)o' to approve the request: ")
            if answer in ["n", "y"]:
                return ApprovalResponse.YES if answer == "y" else ApprovalResponse.CANCEL

    def ui_takeover(self, message: str) -> UiTakeoverResponse:
        print(
            f"\n🤖 UI Takeover required for act_id: {self.current_act_id} inside act_session_id: {self.act_session_id}:"
        )
        print(f"   {message}")
        print("   Please complete the action in the browser...")
        while True:
            answer = input(
                "   Please enter '(d)one' or '(c)ancel' to indicate completion or cancellation of takeover: "
            )
            if answer in ["d", "c"]:
                return UiTakeoverResponse.COMPLETE if answer == "d" else UiTakeoverResponse.CANCEL


def print_email_title(email_app_url: str) -> None:
    """Print the title of the first email in the inbox.

    Args:
        email_app_url: full URL of the email application to log into, and read email from

    """
    task_prompt = (
        "Log into the email web appliation. "
        "Ask for approval to return the number of emails in the inbox. "
        "If approved, return the number of emails in the inbox."
    )
    with NovaAct(
        starting_page=email_app_url,
        tty=False,
        human_input_callbacks=ConsoleBasedHumanInputCallbacks(),
    ) as nova:
        result = nova.act_get(task_prompt)
        print(f"Task completed: {result.response}")


if __name__ == "__main__":
    fire.Fire(print_email_title)
