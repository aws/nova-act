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
"""NovaAct argument parsing and handling utilities."""

from nova_act.cli.core.nova_args import parse_nova_arg, validate_and_coerce_nova_args
from nova_act.cli.core.output import exit_with_error

# NovaAct method-only arguments (not valid for constructor)
METHOD_ONLY_ARGS = frozenset({"max_steps", "model_temperature", "model_top_k", "model_seed", "observation_delay_ms"})


def parse_nova_args(nova_arg: tuple[str, ...]) -> dict[str, object]:
    """Parse and validate nova_arg tuples into dict."""
    if not nova_arg:
        return {}
    try:
        raw_args: dict[str, object] = {}
        for arg in nova_arg:
            key, value = parse_nova_arg(arg)
            raw_args[key] = value
        return validate_and_coerce_nova_args(raw_args)
    except ValueError as e:
        exit_with_error(
            "Invalid NovaAct argument",
            str(e),
            suggestions=[
                "Use format: --nova-arg key=value",
                "Example: --nova-arg headless=true",
                "Example: --nova-arg screen_width=1920",
            ],
        )
        return {}  # Unreachable, but satisfies type checker


def filter_constructor_args(nova_args: dict[str, object]) -> dict[str, object]:
    """Filter nova_args to only constructor-valid arguments.

    Removes method-only parameters (defined in METHOD_ONLY_ARGS) that are
    only valid for act()/act_get() calls, not the NovaAct constructor.

    Args:
        nova_args: Combined dictionary of all --nova-arg parameters

    Returns:
        Dictionary of constructor-valid arguments
    """
    return {k: v for k, v in nova_args.items() if k not in METHOD_ONLY_ARGS}


def filter_method_args(nova_args: dict[str, object]) -> dict[str, object]:
    """Filter nova_args to only method-level arguments.

    Extracts parameters that are only valid for act()/act_get() method calls
    (defined in METHOD_ONLY_ARGS), not the NovaAct constructor.

    Method-only parameters:
    - max_steps: Maximum number of browser automation steps
    - model_temperature: Model temperature for generation
    - model_top_k: Model top-k sampling parameter
    - model_seed: Model random seed
    - observation_delay_ms: Delay between observations

    Args:
        nova_args: Combined dictionary of all --nova-arg parameters

    Returns:
        Dictionary of method-only arguments
    """
    return {k: v for k, v in nova_args.items() if k in METHOD_ONLY_ARGS}
