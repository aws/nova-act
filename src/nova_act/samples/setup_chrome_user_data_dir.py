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
"""Set up a user_data_dir for logged in websites.

See README for more details.

Usage:
python -m nova_act.samples.setup_chrome_user_data_dir --user_data_dir <directory>
"""

import os

import fire  # type: ignore

from nova_act import NovaAct


def main(user_data_dir: str) -> None:
    os.makedirs(user_data_dir, exist_ok=True)

    with NovaAct(starting_page="https://amazon.com/", user_data_dir=user_data_dir, clone_user_data_dir=False):
        input("Log into your websites, then press enter...")

    print(f"User data dir saved to {user_data_dir=}")


if __name__ == "__main__":
    fire.Fire(main)
