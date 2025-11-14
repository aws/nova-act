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
from pydantic import BaseModel, field_validator
from typing_extensions import TypedDict

from nova_act.util.path_validator import validate_allowed_paths


class SecurityOptions(BaseModel):
    allow_file_urls: bool = False
    """Allow the browser to navigate to local file:// urls"""

    allowed_file_upload_paths: list[str] = []
    """List of local filepaths from which file uploads are permitted.

    Examples:
    - ["/home/nova-act/shared/*"] - Allow uploads from specific directory
    - ["/home/nova-act/shared/file.txt"] - Allow uploads with specific filepath
    - ["*"] - Enable file uploads from all paths
    - [] - Disable file uploads (Default)
    """

    @field_validator("allowed_file_upload_paths")
    @classmethod
    def validate_allowed_paths(cls, paths: list[str]) -> list[str]:
        """Validate that all paths in allowed_file_upload_paths are valid."""

        # Throws if a path is not valid
        validate_allowed_paths(paths)
        return paths


class PreviewFeatures(TypedDict, total=False):
    """Experimental features for opt-in."""
