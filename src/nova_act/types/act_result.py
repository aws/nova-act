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
from __future__ import annotations

import dataclasses

from nova_act.types.act_metadata import ActMetadata
from nova_act.types.json_type import JSONType
from nova_act.util.logging import trace_log_lines

"""
Successful outcome of act()
"""


@dataclasses.dataclass(frozen=True)
class ActResult:
    """A result from act()."""

    metadata: ActMetadata

    def __repr__(self) -> str:
        # Get all instance attributes except 'metadata' and 'steps_taken'
        field_names = [
            field.name for field in dataclasses.fields(self) if field.name not in ("metadata", "steps_taken")
        ]

        # Get the values of those instance attributes
        field_values = [getattr(self, field) for field in field_names]

        # Strip starting _ from any field names
        field_names = [field[1:] if field.startswith("_") else field for field in field_names]

        # Build the custom fields string
        custom_fields = "\n    ".join(
            f"{field_name} = {field_value}" for field_name, field_value in zip(field_names, field_values)
        )

        # Indent metadata for visual distinction
        metadata_str = str(self.metadata).replace("\n", "\n    ")

        # If there are custom fields, add them before the metadata
        if custom_fields:
            return f"{self.__class__.__name__}(\n" f"    {custom_fields}\n" f"    metadata = {metadata_str}\n" f")"

        # If no custom fields, just show the metadata
        return f"{self.__class__.__name__}(\n" f"    metadata = {metadata_str}\n" f")"



@dataclasses.dataclass(frozen=True, repr=False)
class ActGetResult(ActResult):
    """A result from act_get()."""

    response: str | None = None
    parsed_response: JSONType | None = None
    valid_json: bool | None = None
    matches_schema: bool | None = None

    def without_response(self) -> ActResultWithoutResponse:
        """Convert to an ActResultWithoutResponse."""
        return ActResultWithoutResponse(
            metadata=self.metadata,
            response=self.response,
            parsed_response=self.parsed_response,
            valid_json=self.valid_json,
            matches_schema=self.matches_schema,
        )


@dataclasses.dataclass(frozen=True, repr=False)
class ActResultWithoutResponse(ActResult):
    """A result from act() without a provided schema."""

    _response: str | None = dataclasses.field(init=False, repr=False)
    _parsed_response: JSONType | None = dataclasses.field(init=False, repr=False)
    _valid_json: bool | None = dataclasses.field(init=False, repr=False)
    _matches_schema: bool | None = dataclasses.field(init=False, repr=False)

    def __init__(
        self,
        metadata: ActMetadata,
        response: str | None = None,
        parsed_response: JSONType | None = None,
        valid_json: bool | None = None,
        matches_schema: bool | None = None,
    ) -> None:
        super().__init__(
            metadata=metadata,
            # fmt: on
        )
        object.__setattr__(self, "_response", response)
        object.__setattr__(self, "_parsed_response", parsed_response)
        object.__setattr__(self, "_valid_json", valid_json)
        object.__setattr__(self, "_matches_schema", matches_schema)

    @staticmethod
    def emit_warning() -> None:
        trace_log_lines(
            "\033[91m"  # warn in red
            "WARNING: Asking Act for a structured extract without providing a schema could lead to undefined "
            "behavior. In future versions, such workflows will fail. Use act_get, or make sure to provide a "
            "schema!"
            "\033[0m"  # reset color
        )

    @property
    def response(self) -> str | None:
        type(self).emit_warning()
        return self._response

    @property
    def parsed_response(self) -> JSONType | None:
        type(self).emit_warning()
        return self._parsed_response

    @property
    def valid_json(self) -> bool | None:
        type(self).emit_warning()
        return self._valid_json

    @property
    def matches_schema(self) -> bool | None:
        type(self).emit_warning()
        return self._matches_schema
