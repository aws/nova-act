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
"""Simple example of modifying customer details in SAP Master customer data management tool.

Usage:
python -m nova_act.samples.sap_master_customer_data_management [--record_video]
"""

import fire  # type: ignore

from nova_act import NovaAct


def main(record_video: bool = False) -> None:
    with NovaAct(
        starting_page="https://democf.saponaws.site/sap/bc/ui5_ui5/ui2/ushell/shells/abap/FioriLaunchpad.html",
        record_video=record_video,
    ) as nova:
        nova.act("wait for user to login")
        nova.act("navigate to Master Data - Business Partners section")
        nova.act("look for 'Manage customer master data' and then click 'Manage customer master data'")
        nova.act("look for search box under Standard view")
        nova.act("search for 'Copenhagen municipality'")
        nova.act("click on 'Copenhagen municipality' on the search results")
        nova.act("look for 'edit' button and then click 'edit'")
        nova.act("scroll down to Standard Address section and change the postal code to 6980")
        nova.act("look for 'save' button and then click 'save'")


if __name__ == "__main__":
    fire.Fire(main)
