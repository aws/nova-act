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
from urllib.parse import urlparse
from urllib.request import url2pathname

from nova_act.types.act_errors import ActActuationError
from nova_act.types.errors import InvalidURL


def validate_file_url(candidate_url: str, allowed_paths: list[str]) -> None:
    """
    Validate that a given file:// url points to a filepath that is within one
    of the given allowed paths

    Args:
        candidate_url: The file:// path to validate
        allowed_paths: List of allowed path patterns (does not include file:// prefix)

    Raises:
        InvalidURL: If the url is not allowed

    Pattern Matching:
    - "*" matches all paths
    - "/path/to/dir/*" matches all files in directory and subdirectories
    - "/path/to/file.txt" matches exact file
    """

    if not candidate_url.startswith("file:"):
        raise InvalidURL(f"Given url is not a file:// URL: '{candidate_url}'")

    candidate_path = _file_url_to_native_path(candidate_url)

    try:
        _validate_file_access_path(
            candidate_path=candidate_path,
            allowed_paths=allowed_paths,
            operation="file url",
            param_name="allowed_file_open_paths",
        )
    except _FileAccessError as e:
        raise InvalidURL(str(e)) from e


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
    try:
        _validate_file_access_path(
            candidate_path=candidate_path,
            allowed_paths=allowed_paths,
            operation="file upload",
            param_name="allowed_file_upload_paths",
        )
    except _FileAccessError as e:
        raise ActActuationError(str(e)) from e


class _FileAccessError(Exception):
    """Internal helper exception, to be mapped to InvalidURL or ActActuationError"""

    pass


def _validate_file_access_path(candidate_path: str, allowed_paths: list[str], operation: str, param_name: str) -> None:
    # Skip if the given list of allowed paths is empty
    if allowed_paths:
        # Universal wildcard allows all uploads
        if "*" in allowed_paths:
            return

        # Normalize the path
        try:
            normalized_candidate_path = _normalize_path(candidate_path)
        except Exception as e:
            raise _FileAccessError(f"Unable to resolve path: '{candidate_path}'. Error: {e}") from e

        # Check against each allowed path
        for allowed_path in allowed_paths:
            try:
                normalized_allowed = _normalize_path(allowed_path)
                allowed_path_str = str(normalized_allowed)
                if _is_path_allowed(normalized_candidate_path, allowed_path_str):
                    # The lexical check above does not resolve symlinks, so a symlink that sits inside
                    # an allowed location but points outside it would pass. Resolve symlinks on both
                    # sides and re-check containment: the real candidate must still be within the real
                    # allowed root (the leading non-wildcard portion of the pattern). This covers the
                    # directory (``/dir/*``) and glob (``/dir/*.ext``, ``/dir/*/file``) patterns as
                    # well as exact-file patterns. Both sides are resolved so a legitimately symlinked
                    # allowed location (for example /tmp -> /private/tmp) still matches.
                    # Pass the normalized candidate (home-expanded and made absolute): os.path.realpath
                    # does not expand ``~``, so handing it the raw candidate would resolve a ``~/...``
                    # path relative to the cwd and wrongly reject an otherwise-allowed path.
                    if not _real_path_within_allowed_root(str(normalized_candidate_path), allowed_path_str):
                        continue
                    return
            except Exception:
                # Skip invalid patterns in the allowlist
                continue

    # No match found - block the operation
    raise _FileAccessError(
        f"Blocked {operation}: given path is not in the list of allowed paths: '{candidate_path}'\n"
        f"Allowed path list: {allowed_paths}\n"
        f"To allow, set NovaAct parameter "
        f"security_options=SecurityOptions({param_name}=['/path/to/directory/*'])"
    )


def validate_allowed_paths(allowed_paths: list[str]) -> None:
    """
    Checks that the list of allowed paths is valid and doesn't contain illegal patterns.

    Validates:
    - No null bytes in paths
    - No empty or whitespace-only paths
    - Paths can be normalized successfully
    - No path traversal patterns
    - Wildcards only allowed in the filename, not the directory path

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

        # Disallow wildcard characters in directory path (only allowed in filename)
        if "*" in path and path != "*":
            path_obj = Path(path)
            # Check if any parent directory contains a wildcard
            for parent in path_obj.parents:
                if "*" in str(parent):
                    raise ValueError(
                        f"Invalid allowed path: '{path}'. Wildcard characters are only allowed in the filename, "
                        f"not in the directory path"
                    )

        # Try to normalize the path - this will catch most invalid paths
        try:
            normalized = _normalize_path(path)
            # Verify the normalized path is valid by converting to string
            str(normalized)
        except Exception as e:
            raise ValueError(f"Invalid allowed path: '{path}'. Error: {e}") from e


def _file_url_to_native_path(file_url: str) -> str:
    """
    Convert a file:// URL to an OS-native filesystem path.

    Correctly handles Windows drive letters (e.g. "file:///C:/foo" -> "C:\\foo") and
    POSIX paths (e.g. "file:///tmp/foo" -> "/tmp/foo"), including malformed URLs with
    extra leading slashes (e.g. "file:////tmp/foo" -> "/tmp/foo").

    Note: once the minimum supported Python version is 3.13, this can be replaced
    with pathlib.Path.from_uri().

    Args:
        file_url: A file:// URL

    Returns:
        OS-native filesystem path string
    """
    # Extract the path component from the file:// URL.
    url_path = urlparse(file_url).path

    # Collapse any leading duplicate slashes down to a single slash. urlparse leaves
    # them behind for malformed URLs with extra slashes (e.g. "file:////tmp/foo"
    # parses to "//tmp/foo"), which would otherwise break path matching.
    while url_path.startswith("//"):
        url_path = url_path[1:]

    return url2pathname(url_path)


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


def _allowed_root_prefix(allowed_path_str: str) -> str:
    """Return the leading portion of a normalized allowed pattern that contains no wildcard.

    This is the fixed directory (or exact file) the pattern is anchored to, used as the containment
    root for the symlink resolve-and-recheck. Examples: ``/dir/*`` and ``/dir/*.ext`` and
    ``/dir/*/file.txt`` all anchor to ``/dir``; an exact file ``/dir/file.txt`` anchors to itself.

    Args:
        allowed_path_str: The normalized allowed pattern.

    Returns:
        The leading wildcard-free path prefix (at least the filesystem root).
    """
    root_parts: list[str] = []
    for part in Path(allowed_path_str).parts:
        if "*" in part:
            break
        root_parts.append(part)
    return str(Path(*root_parts)) if root_parts else os.sep


def _real_path_within_allowed_root(candidate_path: str, allowed_path_str: str) -> bool:
    """Re-check containment after resolving symbolic links on both sides.

    ``_is_path_allowed`` matches lexically and does not resolve symlinks, so a symlink inside an
    allowed location whose target lies outside it would pass. This gate resolves the real target of
    both the candidate and the allowed root (via ``os.path.realpath``) and confirms the real
    candidate is still contained within (or, for an exact-file pattern, equal to) the real allowed
    root. Both sides are resolved so an allowed location that is itself reached through a symlink
    still matches.

    Args:
        candidate_path: The normalized candidate path (home-expanded and absolute, but not yet
            symlink-resolved). It must be home-expanded because ``os.path.realpath`` does not expand
            ``~``.
        allowed_path_str: The normalized allowed pattern that matched lexically.

    Returns:
        True if the resolved candidate is still within the resolved allowed root, False otherwise.
    """
    real_candidate = Path(os.path.realpath(candidate_path))
    real_allowed_root = os.path.realpath(_allowed_root_prefix(allowed_path_str))
    try:
        # relative_to returns "." for an exact match (exact-file pattern) and a subpath for a
        # directory/glob pattern; a target outside the root raises ValueError.
        real_candidate.relative_to(real_allowed_root)
        return True
    except ValueError:
        return False


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
