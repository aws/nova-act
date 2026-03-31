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
"""JSON schema parsing utilities for browser CLI commands."""

import json
from collections.abc import Mapping

from pydantic import JsonValue

from nova_act.cli.core.output import exit_with_error
from nova_act.util.jsonschema import BOOL_SCHEMA, STRING_SCHEMA


def _resolve_schema_shortcut(schema_lower: str) -> dict[str, JsonValue] | None:
    """Resolve enum shortcuts to schema constants."""
    if schema_lower == "bool" or schema_lower == "boolean":
        return dict(BOOL_SCHEMA)
    elif schema_lower == "string":
        return dict(STRING_SCHEMA)
    return None


def _parse_json_with_error_handling(schema: str) -> dict[str, JsonValue]:
    """Parse JSON string with user-friendly error handling."""
    try:
        result: dict[str, JsonValue] = json.loads(schema)
        return result
    except json.JSONDecodeError as e:
        exit_with_error(
            "Invalid JSON schema",
            str(e),
            suggestions=[
                "Ensure schema is valid JSON",
                "Use enum shortcuts: --schema bool, --schema string",
                'Example: --schema \'{"type": "object", "properties": {"title": {"type": "string"}}}\'',
                "Check for proper escaping of quotes",
            ],
        )
        return {}  # Unreachable, but satisfies type checker


def parse_json_schema(schema: str | None) -> Mapping[str, JsonValue] | None:
    """Parse JSON schema string with error handling.

    Supports both enum shortcuts and full JSON schemas:
    - Enum shortcuts: 'bool', 'string'
    - Full JSON: '{"type": "object", "properties": {...}}'
    """
    if not schema or not schema.strip():
        return None

    schema_lower = schema.lower().strip()
    shortcut_result = _resolve_schema_shortcut(schema_lower)
    if shortcut_result is not None:
        return shortcut_result

    return _parse_json_with_error_handling(schema)
