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
"""AgentCore-specific workflow validation utilities for entry point and source validation."""

import ast
import logging
from pathlib import Path

from nova_act.cli.core.error_detection import (
    get_entry_point_missing_main_message,
    get_entry_point_missing_parameter_message,
)
from nova_act.cli.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# File extensions and names
_PYTHON_FILE_EXTENSION = ".py"
_DEFAULT_ENTRY_POINT = "main.py"


def validate_entry_point_file(entry_point_path: str) -> None:
    """Validate entry point file exists and is Python."""
    entry_path = Path(entry_point_path)
    if not entry_path.exists():
        raise ConfigurationError(f"Entry point file does not exist: {entry_point_path}")
    if not entry_point_path.endswith(_PYTHON_FILE_EXTENSION):
        raise ConfigurationError(f"Entry point must be a Python file (.py): {entry_point_path}")


class AgentCoreSourceValidator:
    """Validates AgentCore workflow source files and entry points using stateful validation.

    Attributes:
        source_path (Path): Validated source directory containing workflow files
        entry_point (str): Resolved entry point filename (auto-detected or provided)
        skip_validation (bool): Whether to skip main() function validation
    """

    def __init__(self, source_dir: str, entry_point: str | None = None, skip_validation: bool = False):
        """Initialize validator with source directory and validation options."""
        self.source_path = self._validate_source_directory(source_dir)
        self.entry_point = entry_point or self._resolve_entry_point()
        self.skip_validation = skip_validation

    def validate(self) -> None:
        """Perform complete validation of source directory and entry point."""
        logger.info("Validating source code and entry point...")
        self.validate_entry_point_file()
        if not self.skip_validation:
            self._validate_main_function()
        logger.info("Source code validation passed")

    def _validate_source_directory(self, source_dir: str) -> Path:
        """Validate source directory exists."""
        source_path = Path(source_dir)
        if not source_path.exists() or not source_path.is_dir():
            raise ConfigurationError(f"Source directory does not exist: {source_dir}")
        return source_path

    def _resolve_entry_point(self) -> str:
        """Resolve entry point filename."""
        if self._has_main_py():
            logger.info(f"Auto-detected entry point: {_DEFAULT_ENTRY_POINT}")
            return _DEFAULT_ENTRY_POINT
        return self._detect_single_python_file()

    def validate_entry_point_file(self) -> None:
        """Validate entry point file exists and is Python."""
        entry_point_path = self.source_path / self.entry_point
        validate_entry_point_file(str(entry_point_path))

    def _validate_main_function(self) -> None:
        """Validate main() function exists and accepts parameters using AST analysis."""
        entry_point_path = self.source_path / self.entry_point

        try:
            content = entry_point_path.read_text(encoding="utf-8")
        except Exception as e:
            raise ConfigurationError(f"Cannot read entry point file {entry_point_path}: {e}") from e

        main_node = self._find_top_level_main(content, entry_point_path)

        if main_node is None:
            message = get_entry_point_missing_main_message(entry_point_path=entry_point_path)
            raise ConfigurationError(message)

        if len(main_node.args.args) == 0:
            message = get_entry_point_missing_parameter_message(entry_point_path=entry_point_path)
            raise ConfigurationError(message)

        logger.info(f"Entry point validation passed: {entry_point_path}")

    def _has_main_py(self) -> bool:
        """Check if main.py exists in source path."""
        return (self.source_path / _DEFAULT_ENTRY_POINT).exists()

    def _detect_single_python_file(self) -> str:
        """Detect single Python file or raise error for multiple files."""
        python_files = list(self.source_path.glob("*.py"))

        if len(python_files) == 0:
            raise ConfigurationError(f"No Python files found in source directory: {self.source_path}")
        elif len(python_files) == 1:
            entry_point = python_files[0].name
            logger.info(f"Auto-detected entry point: {entry_point}")
            return entry_point
        else:
            py_file_names = sorted([f.name for f in python_files])
            raise ConfigurationError(
                f"Multiple Python files found, please specify --entry-point: {', '.join(py_file_names)}"
            )

    def _find_top_level_main(
        self, content: str, entry_point_path: Path
    ) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
        """Find a top-level main() function definition using AST analysis.

        Only examines top-level nodes (not nested functions). Handles both
        sync and async function definitions.

        Returns:
            The AST node for main() if found, None otherwise.

        Raises:
            ConfigurationError: If the source file contains invalid Python syntax.
        """
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            raise ConfigurationError(f"Cannot parse entry point file {entry_point_path}: {e}") from e

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "main":
                return node
        return None
