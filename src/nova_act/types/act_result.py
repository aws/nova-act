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
import dataclasses

from nova_act.types.act_metadata import ActMetadata
from nova_act.types.json_type import JSONType

"""
Successful outcome of act()
"""


@dataclasses.dataclass(frozen=True)
class ActResult:

    metadata: ActMetadata

    response: str | None = None
    parsed_response: JSONType | None = None
    valid_json: bool | None = None
    matches_schema: bool | None = None

    def __repr__(self) -> str:
        # Get all instance attributes except 'metadata'
        fields = [field.name for field in dataclasses.fields(self) if field.name != "metadata"]

        # Build the custom fields string
        custom_fields = "\n    ".join(f"{field} = {getattr(self, field)}" for field in fields)

        # Indent metadata for visual distinction
        metadata_str = str(self.metadata).replace("\n", "\n    ")

        # If there are custom fields, add them before the metadata
        if custom_fields:
            return f"{self.__class__.__name__}(\n" f"    {custom_fields}\n" f"    metadata = {metadata_str}\n" f")"

        # If no custom fields, just show the metadata
        return f"{self.__class__.__name__}(\n" f"    metadata = {metadata_str}\n" f")"
