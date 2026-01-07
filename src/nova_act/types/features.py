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
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from typing_extensions import TypedDict

from nova_act.util.logging import setup_logging
from nova_act.util.path_validator import validate_allowed_paths

_LOGGER = setup_logging(__name__)


class SecurityOptions(BaseModel):
    # Disallow extra parameters
    model_config = ConfigDict(extra="forbid")

    allow_file_urls: bool = Field(
        default=False,
        deprecated=True,
        description="allow_file_urls is deprecated; use allowed_file_open_paths instead",
    )
    """Note that use of a boolean to enable all file:// urls is deprecated as it was too coarse-grained
    """

    allowed_file_open_paths: list[str] = Field(default_factory=list, validate_default=True)
    """List of local file:// paths which the agent is allowed to navigate to

    Examples:
    - ["/home/nova-act/shared/*"] - Allow access to files in a specific directory
    - ["/home/nova-act/shared/file.txt"] - Allow access to a specific filepath
    - ["*"] - Enable file:// access to app paths
    - [] - Disable file access (Default)
    """

    allowed_file_upload_paths: list[str] = []
    """List of local filepaths from which file uploads are permitted.

    Examples:
    - ["/home/nova-act/shared/*"] - Allow uploads from specific directory
    - ["/home/nova-act/shared/file.txt"] - Allow uploads with specific filepath
    - ["*"] - Enable file uploads from all paths
    - [] - Disable file uploads (Default)
    """

    @field_validator("allowed_file_open_paths", mode="before")
    @classmethod
    def set_allowed_file_open_paths_from_deprecated(  # type: ignore[explicit-any]
        cls, allowed_file_open_paths: list[str], info: ValidationInfo
    ) -> list[str]:
        # If allow_file_urls=True and allowed_file_open_paths is not set, then
        # set allowed_file_open_paths=['*'] to maintain backwards compatibility

        if info.data.get("allow_file_urls", False):
            _LOGGER.warning("The 'allow_file_urls' argument has been deprecated. Use 'allowed_file_open_paths' instead")
            if len(allowed_file_open_paths) == 0:
                return ["*"]
        return allowed_file_open_paths

    @field_validator("allowed_file_open_paths", "allowed_file_upload_paths", mode="after")
    @classmethod
    def validate_file_open_paths(cls, paths: list[str]) -> list[str]:
        """Validate that all paths in allowed_file_upload_paths are valid."""

        # Throws if a path is not valid
        validate_allowed_paths(paths)
        return paths


class PreviewFeatures(TypedDict, total=False):
    """Experimental features for opt-in."""
