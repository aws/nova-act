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

import json
from typing import Mapping

import jsonschema

from nova_act.types.act_result import ActGetResult, ActResult
from nova_act.types.json_type import JSONType

BOOL_SCHEMA = {"type": "boolean"}
STRING_SCHEMA = {"type": "string"}


def validate_jsonschema_schema(schema: Mapping[str, JSONType]) -> None:
    try:
        jsonschema.Draft7Validator.check_schema(schema)
    except jsonschema.SchemaError as e:
        raise jsonschema.SchemaError("Schema provided isn't a valid jsonschema") from e


def add_schema_to_prompt(prompt: str, schema: Mapping[str, JSONType]) -> str:
    schema_str: str = json.dumps(schema)
    return f"{prompt}, format output with jsonschema: {schema_str}"


def populate_json_schema_response(result: ActResult, schema: Mapping[str, JSONType]) -> ActGetResult:
    response = result.response if isinstance(result, ActGetResult) else None
    if not response:
        return ActGetResult(
            response=response,
            parsed_response=None,
            valid_json=False,
            matches_schema=False,
            metadata=result.metadata,
        )
    try:
        if schema != STRING_SCHEMA:
            parsed_response = json.loads(response)
        else:
            parsed_response = response
        jsonschema.validate(instance=parsed_response, schema=schema)
    except json.JSONDecodeError:
        return ActGetResult(
            response=response,
            parsed_response=None,
            valid_json=False,
            matches_schema=False,
            metadata=result.metadata,
        )
    except jsonschema.ValidationError:
        return ActGetResult(
            response=response,
            parsed_response=parsed_response,
            valid_json=True,
            matches_schema=False,
            metadata=result.metadata,
        )
    return ActGetResult(
        response=response,
        parsed_response=parsed_response,
        valid_json=True,
        matches_schema=True,
        metadata=result.metadata,
    )
