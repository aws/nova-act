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

from nova_act.types.errors import InvalidPath


def safe_relative_path(path: str, base_dir: str) -> str:
    """Get a relative path while blocking path traversal attempts."""
    # Resolve and normalize paths
    abs_path = os.path.abspath(os.path.join(base_dir, path))
    abs_base = os.path.abspath(base_dir)

    # Ensure the path is within the base directory
    if not abs_path.startswith(abs_base + os.sep):
        raise InvalidPath(f"Path traversal attempt detected: {path}")

    return os.path.relpath(abs_path, abs_base)
