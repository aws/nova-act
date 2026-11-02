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
"""Secrets type for providing actuators with sensitive values without sending them to the backend."""

import re
from dataclasses import dataclass, field

from nova_act.util.logging import setup_logging

_LOGGER = setup_logging(__name__)

MASKED_VALUE = "***"


@dataclass(frozen=True)
class Secrets:
    """Container for sensitive values that actuators can reference without sending them to the backend."""

    data: dict[str, str]
    prefix: str = "{{"
    suffix: str = "}}"
    _KEY_PATTERN: re.Pattern[str] = field(init=False, repr=False, compare=False, default=re.compile(r"^\w+$"))
    _pattern: re.Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.data:
            raise ValueError("Secrets data must not be empty")
        key_pattern = self._KEY_PATTERN.pattern
        for key in self.data:
            if not self._KEY_PATTERN.match(key):
                raise ValueError(f"Secret key '{key}' does not match required placeholder pattern: {key_pattern}")
        escaped_prefix = re.escape(self.prefix)
        escaped_suffix = re.escape(self.suffix)
        key_expr = key_pattern.strip("^$")
        object.__setattr__(self, "_pattern", re.compile(f"{escaped_prefix}({key_expr}){escaped_suffix}"))

    def __repr__(self) -> str:
        masked = {k: MASKED_VALUE for k in self.data}
        return f"Secrets(data={masked}, prefix={self.prefix!r}, suffix={self.suffix!r})"

    def __format__(self, format_spec: str) -> str:
        return format(repr(self), format_spec)

    def format_placeholder(self, key: str) -> str:
        """Return the placeholder token for a key, e.g. ``{{key}}``."""
        return f"{self.prefix}{key}{self.suffix}"

    def resolve(self, value: str) -> str:
        """Replace placeholder tokens in value with their secret values."""

        def _replace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in self.data:
                raise ValueError(
                    f"Placeholder '{self.format_placeholder(key)}' not found in secrets. "
                    f"Available keys: {list(self.data.keys())}"
                )
            _LOGGER.debug(f"Resolved secret placeholder: {self.format_placeholder(key)}")
            return self.data[key]

        return self._pattern.sub(_replace, value)
