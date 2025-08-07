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
import random

import fire  # type: ignore

from nova_act import DefaultNovaLocalBrowserActuator, JSONSerializable, NovaAct

"""
python -m nova_act.samples.custom_actuator --headless
"""


CELEBRATIONS = [
    """
    ╔═════════════════╗
    ║  🎉 CLICK! 🎉   ║
    ╚═════════════════╝
    """,
    """
       *    *
      * ✨ *
     *  🎯  *
      * ✨ *
       *    *
    """,
    """
      .--------.
     /          \\
    |   CLICK!   |
     \\          /
      '--------'
    """,
    """
    ⚡️⚡️⚡️ CLICK! ⚡️⚡️⚡️
    """,
    """
       .---.
      /   🎯 \\
     | BULLSEYE |
      \\     /
       '---'
    """,
]


class CelebratoryActuator(DefaultNovaLocalBrowserActuator):
    """An actuator that celebrates each click with ASCII art in the console.
    This is a demo for more useful hooks you can dream up
    """

    def agent_click(
        self, box: str, click_type: str | None = None, click_options: str | None = None
    ) -> JSONSerializable:
        # Show celebration before the click
        self._celebrate()
        # Delegate to base actuator
        super().agent_click(box, click_type, click_options)
        return None

    def _celebrate(self) -> None:
        """Show a random ASCII celebration in the console."""
        celebration = random.choice(CELEBRATIONS)

        # Print with colors if supported
        try:
            # ANSI color codes for colorful output
            colors = [
                "\033[91m",  # Red
                "\033[92m",  # Green
                "\033[93m",  # Yellow
                "\033[94m",  # Blue
                "\033[95m",  # Magenta
                "\033[96m",  # Cyan
            ]
            reset = "\033[0m"  # Reset color

            color = random.choice(colors)
            print(f"{color}{celebration}{reset}")
        except Exception:
            # Fallback if terminal doesn't support colors
            print(celebration)


def main(headless: bool = False) -> None:
    with NovaAct(starting_page="https://www.amazon.com", actuator=CelebratoryActuator, headless=headless) as nova:
        nova.act("search for a coffee maker")
        nova.act("click on the first option")


if __name__ == "__main__":
    fire.Fire(main)
