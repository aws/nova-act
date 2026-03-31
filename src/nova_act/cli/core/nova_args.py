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
"""Utilities for parsing and validating NovaAct constructor arguments from CLI."""

import inspect
from typing import get_type_hints

from nova_act import NovaAct


def parse_nova_arg(arg_string: str) -> tuple[str, str]:
    """Parse a single --nova-arg key=value string.

    Args:
        arg_string: String in format "key=value"

    Returns:
        Tuple of (key, value) as strings

    Raises:
        ValueError: If format is invalid
    """
    if "=" not in arg_string:
        raise ValueError(f"Invalid format: '{arg_string}'. Expected 'key=value'")

    key, value = arg_string.split("=", 1)
    key = key.strip()
    value = value.strip()

    if not key:
        raise ValueError(f"Empty key in: '{arg_string}'")

    return key, value


def coerce_type(value: str, target_type: type) -> object:
    """Coerce string value to target type.

    Args:
        value: String value to coerce
        target_type: Target type to coerce to

    Returns:
        Coerced value

    Raises:
        ValueError: If coercion fails
    """
    # Handle None/Optional types
    if value.lower() == "none":
        return None

    # Handle bool specially (avoid bool("false") == True)
    if target_type is bool:
        if value.lower() in ("true", "1", "yes"):
            return True
        elif value.lower() in ("false", "0", "no"):
            return False
        else:
            raise ValueError(f"Cannot convert '{value}' to bool")

    # Handle int
    if target_type is int:
        return int(value)

    # Handle float
    if target_type is float:
        return float(value)

    # Handle str (no conversion needed)
    if target_type is str:
        return value

    # For other types, attempt direct conversion
    try:
        return target_type(value)
    except Exception as e:
        raise ValueError(f"Cannot convert '{value}' to {target_type.__name__}: {e}")


def validate_and_coerce_nova_args(args: dict[str, object]) -> dict[str, object]:
    """Validate and coerce NovaAct constructor and method arguments.

    Validates arguments against both NovaAct.__init__ and NovaAct.act/act_get methods.
    Some parameters are only valid for method calls (max_steps, model_temperature, etc.)

    Args:
        args: Dictionary of argument names to string values

    Returns:
        Dictionary of validated and type-coerced arguments

    Raises:
        ValueError: If any argument is invalid
    """
    valid_params, type_hints = _gather_nova_act_params()

    validated: dict[str, object] = {}
    for key, value in args.items():
        _validate_param_name(key, valid_params)
        validated[key] = _coerce_param(key, str(value), type_hints)
    return validated


def _gather_nova_act_params() -> tuple[dict[str, inspect.Parameter], dict[str, type]]:
    """Gather valid parameter names and type hints from NovaAct.__init__ and act()."""
    sig = inspect.signature(NovaAct.__init__)
    valid_params = {name: param for name, param in sig.parameters.items() if name != "self"}

    try:
        type_hints: dict[str, type] = get_type_hints(NovaAct.__init__)
    except Exception:
        type_hints = {}

    try:
        act_sig = inspect.signature(NovaAct.act)
        act_params = {name: param for name, param in act_sig.parameters.items() if name != "self"}
        act_type_hints = get_type_hints(NovaAct.act)
        valid_params.update(act_params)
        type_hints.update(act_type_hints)
    except Exception:
        pass

    return valid_params, type_hints


def _validate_param_name(key: str, valid_params: dict[str, inspect.Parameter]) -> None:
    """Raise ValueError if key is not a valid NovaAct parameter."""
    if key not in valid_params:
        valid_names = ", ".join(sorted(valid_params.keys()))
        raise ValueError(
            f"Invalid argument '{key}' for NovaAct constructor or methods.\n" f"Valid arguments: {valid_names}"
        )


def _coerce_param(key: str, value: str, type_hints: dict[str, type]) -> object:
    """Coerce a single parameter value to its target type based on type hints."""
    param_type = type_hints.get(key)
    if param_type is None:
        return value

    # Handle Union/Optional types (e.g., str | None)
    if hasattr(param_type, "__args__"):
        types = [t for t in param_type.__args__ if t is not type(None)]
        if types:
            param_type = types[0]

    if isinstance(param_type, type):
        try:
            return coerce_type(value, param_type)
        except ValueError as e:
            raise ValueError(f"Invalid value for '{key}': {e}")

    return value
