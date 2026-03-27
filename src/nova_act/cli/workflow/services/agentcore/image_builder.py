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
"""AgentCore workflow building operations."""

import re
import shutil
import tempfile
from pathlib import Path

from nova_act.cli.core.exceptions import ImageBuildError
from nova_act.cli.workflow.utils.docker_builder import DockerBuilder

_TEMP_TEMPLATE_PREFIX = "agentcore-templates-"


class BuildContextPreparer:
    """Prepares build context for AgentCore workflow container images."""

    def __init__(
        self,
        image_tag: str,
        project_path: str,
        entry_point: str,
        region: str,
        build_dir: Path | None = None,
        force: bool = False,
    ):
        self.image_tag = image_tag
        self.project_path = project_path
        self.entry_point = entry_point
        self.region = region
        self.build_dir: Path | None = build_dir
        self.force = force

    def prepare_build_context(self) -> Path:
        """Prepare build context directory with templates and project files.

        Returns the path to the ready-to-build directory. Caller is responsible for cleanup.
        """
        self._validate_build_requirements()

        temp_template_dir = self._create_processed_template_dir()

        try:
            builder = DockerBuilder(image_tag=self.image_tag, build_dir=self.build_dir, force=self.force)
            builder.build_dir = builder.ensure_build_directory()
            builder.prepare_build_dir(project_path=self.project_path, template_dir=temp_template_dir)

            if builder.original_build_dir is not None:
                builder.save_build_info_file(self.project_path)

            return builder.build_dir
        finally:
            self._cleanup_temp_template_dir(temp_template_dir)

    def _cleanup_temp_template_dir(self, temp_template_dir: Path) -> None:
        """Clean up temporary template directory if we created one."""
        if not self.build_dir and _TEMP_TEMPLATE_PREFIX in str(temp_template_dir):
            shutil.rmtree(temp_template_dir)

    def _validate_build_requirements(self) -> None:
        """Validate that project path contains required files for building."""
        if not self.entry_point or not self.entry_point.strip():
            raise ImageBuildError("Entry point cannot be empty")

        project_path_obj = Path(self.project_path)
        if not project_path_obj.exists():
            raise ImageBuildError(f"Project path does not exist: {self.project_path}")

        if project_path_obj.is_file():
            if project_path_obj.name != self.entry_point:
                raise ImageBuildError(
                    f"Single file name '{project_path_obj.name}' must match entry point '{self.entry_point}'"
                )
            return

        entry_point_path = project_path_obj / self.entry_point
        if not entry_point_path.exists():
            raise ImageBuildError(f"Entry point file does not exist: {entry_point_path}")

    def _create_processed_template_dir(self) -> Path:
        """Create template directory with processed Dockerfile."""
        template_dir = Path(__file__).parent / "templates"

        if self.build_dir:
            # Use build_dir/templates when build_dir is specified
            temp_dir = self.build_dir / "templates"
            temp_dir.mkdir(parents=True, exist_ok=True)
        else:
            # Use temporary directory when build_dir is None
            temp_dir = Path(tempfile.mkdtemp(prefix=_TEMP_TEMPLATE_PREFIX))

        # Copy all template files
        shutil.copytree(src=template_dir, dst=temp_dir, dirs_exist_ok=True)

        # Process Dockerfile with entry point replacement
        dockerfile_path = temp_dir / "Dockerfile"
        self._update_dockerfile_entry_point(dockerfile_path=dockerfile_path)

        return temp_dir

    def _update_dockerfile_entry_point(self, dockerfile_path: Path) -> None:
        """Update Dockerfile template variables (entry point, region)."""
        content = dockerfile_path.read_text()
        content = re.sub(pattern=r"\{\{entry_point\}\}", repl=self.entry_point, string=content)
        content = re.sub(pattern=r"\{\{region\}\}", repl=self.region, string=content)
        dockerfile_path.write_text(content)
