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
import os
from pathlib import Path

from nova_act.types.act_errors import ActActuationError


def validate_file_upload_path(candidate_path: str, allowed_paths: list[str]) -> None:
    """
    Validate that the given filepath is within at least one of the given allowed paths

    Args:
        candidate_path: The file or directory path to validate
        allowed_paths: List of allowed path patterns

    Raises:
        ActActuationError: If the path is not allowed

    Pattern Matching:
    - "*" matches all paths
    - "/path/to/dir/*" matches all files in directory and subdirectories
    - "/path/to/file.txt" matches exact file
    """

    # Skip if the given list of allowed paths is empty
    if allowed_paths:

        # Universal wildcard allows all uploads
        if "*" in allowed_paths:
            return

        # Normalize the path
        try:
            normalized_candidate_path = _normalize_path(candidate_path)
        except Exception as e:
            raise ActActuationError(f"Unable to resolve path: '{candidate_path}'. Error: {e}")

        # Check against each allowed path
        for allowed_path in allowed_paths:
            try:
                normalized_allowed = _normalize_path(allowed_path)
                if _is_path_allowed(normalized_candidate_path, str(normalized_allowed)):
                    return
            except Exception:
                # Skip invalid patterns in the allowlist
                continue

    # No match found - block the operation
    raise ActActuationError(
        f"Blocked file upload: given path is not in the list of allowed paths: '{candidate_path}'\n"
        f"Allowed path list: {allowed_paths}\n"
        f"To allow, set NovaAct parameter "
        f"security_options=SecurityOptions(allowed_file_upload_paths=['/path/to/directory/*'])"
    )


def validate_allowed_paths(allowed_paths: list[str]) -> None:
    """
    Checks that the list of allowed paths is valid and doesn't contain illegal patterns.

    Validates:
    - No null bytes in paths
    - No empty or whitespace-only paths
    - Paths can be normalized successfully
    - No path traversal patterns

    Args:
        allowed_paths: List of path patterns to validate

    Raises:
        ValueError: If any of the paths are invalid or contain illegal patterns
    """
    for path in allowed_paths:
        # Check for empty or whitespace-only paths
        if not path or not path.strip():
            raise ValueError("Invalid allowed path: path cannot be empty or whitespace-only")

        # To keep things simple, disallow path traversal patterns in allowed paths
        if ".." in path:
            raise ValueError(
                f"Invalid allowed path: '{path}'. Path traversal patterns (..) are not allowed in the allowlist"
            )

        # Try to normalize the path - this will catch most invalid paths
        try:
            normalized = _normalize_path(path)
            # Verify the normalized path is valid by converting to string
            str(normalized)
        except Exception as e:
            raise ValueError(f"Invalid allowed path: '{path}'. Error: {e}") from e


def _normalize_path(path: str) -> Path:
    """
    Normalize a file path to absolute form and remove path traversal sequences.

    - Converts to absolute path
    - Expands user home directory (~)
    - Removes relative path traversal (../)
    - Does NOT resolve symbolic links

    Args:
        path: Path to normalize

    Returns:
        Normalized absolute Path object

    Raises:
        ValueError: If path contains null bytes or other invalid characters
    """
    # Check for null bytes before any Path operations
    if "\x00" in path:
        raise ValueError("Path contains null byte")

    # Handle universal wildcard as special case
    if path == "*":
        return Path(os.sep, "*")

    # Convert to absolute, expand user, and remove ../ traversals
    # Note that we aren't using Path.resolve() to avoid unpacking symlinks
    path = os.path.normpath(os.path.abspath(os.path.expanduser(path)))

    return Path(path)


def _is_path_allowed(candidate_file_path: Path, allowed_path_str: str) -> bool:
    """
    Check if a normalized file path matches an allowed path pattern.

        Args:
        file_path: Normalized file path to check
        allowed_path: Normalized allowed path pattern

    Returns:
        True if the file path is allowed, False otherwise
    """
    # Handle directory wildcard pattern
    if allowed_path_str.endswith("*"):
        allowed_dir = allowed_path_str[:-1]

        # Use Path for reliable path comparison to prevent traversal
        try:
            # Check if file_path is relative to allowed_dir (prevents traversal)
            candidate_file_path.relative_to(allowed_dir)
            return True  # Path is within allowed directory
        except ValueError:
            # relative_to raised ValueError, meaning file_path is not under allowed_dir
            return False  # Path escapes allowed directory
    else:
        # Handle file match
        return candidate_file_path.match(allowed_path_str)
