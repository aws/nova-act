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
"""Generic Docker build operations."""

import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Set

from nova_act.cli.core.constants import BUILD_DIR_PREFIX
from nova_act.cli.core.exceptions import ImageBuildError

logger = logging.getLogger(__name__)


class DockerBuilder:
    """Builds Docker images using generic build configuration."""

    def __init__(self, image_tag: str, build_dir: Path | None = None, force: bool = False):
        self.image_tag = image_tag
        self.original_build_dir = build_dir
        self.build_dir: Path | None = build_dir
        self.force = force

    def build(self, project_path: str, template_dir: Path) -> str:
        """Build Docker image from project and template."""
        logger.info(f"Starting Docker build for image: {self.image_tag}")
        logger.info(f"Project path: {project_path}")
        logger.info(f"Template directory: {template_dir}")

        try:
            self.build_dir = self._ensure_build_directory()
            logger.info(f"Build context directory: {self.build_dir}")

            self._prepare_build_dir(project_path=project_path, template_dir=template_dir)
            self._build_docker_image()

            if self.original_build_dir is not None:
                self._save_build_info_file(project_path)
                logger.info(f"Build artifacts preserved in: {self.build_dir}")

            logger.info(f"Docker build completed successfully: {self.image_tag}")
            return self.image_tag
        finally:
            self._cleanup_if_needed()

    def _ensure_build_directory(self) -> Path:
        """Create build directory."""
        if self.build_dir:
            if self.build_dir.exists() and not self.force:
                raise ImageBuildError(f"Build directory exists: {self.build_dir}")
            self.build_dir.mkdir(parents=True, exist_ok=True)
            return self.build_dir
        return Path(tempfile.mkdtemp(prefix=BUILD_DIR_PREFIX))

    def _prepare_build_dir(self, project_path: str, template_dir: Path) -> None:
        """Prepare build directory with templates and project files."""
        # Copy template files first to let project files override
        self._copy_template_files(template_dir=template_dir)
        self._copy_project_files(project_path=project_path, template_dir=template_dir)

    def _copy_template_files(self, template_dir: Path) -> None:
        """Copy all files from template directory."""
        assert self.build_dir is not None
        logger.info(f"Copying template files from: {template_dir}")

        for item in template_dir.iterdir():
            if item.is_file():
                shutil.copy(src=item, dst=self.build_dir / item.name)
            elif item.is_dir():
                shutil.copytree(src=item, dst=self.build_dir / item.name, dirs_exist_ok=True)

        logger.info("Template files copied to build context")

    def _copy_project_files(self, project_path: str, template_dir: Path) -> None:
        """Copy project files to build directory."""
        logger.info(f"Copying project files from: {project_path}")

        project_path_obj = Path(project_path)
        template_files = self._get_template_file_names(template_dir=template_dir)

        if project_path_obj.is_file():
            self._copy_single_file(project_file=project_path_obj, template_files=template_files)
            logger.info("Copied single project file")
        else:
            self._copy_directory_contents(project_dir=project_path_obj, template_files=template_files)
            logger.info("Copied project directory contents")

    def _get_template_file_names(self, template_dir: Path) -> Set[str]:
        """Get template file names from directory structure."""
        template_files = set()
        for item in template_dir.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(template_dir)
                template_files.add(str(rel_path))
        return template_files

    def _copy_single_file(self, project_file: Path, template_files: Set[str]) -> None:
        """Copy single file deployment."""
        assert self.build_dir is not None
        if project_file.name in template_files:
            self._log_template_override_warning(filename=project_file.name)
        shutil.copy(src=project_file, dst=self.build_dir / project_file.name)

    def _copy_directory_contents(self, project_dir: Path, template_files: Set[str]) -> None:
        """Copy directory contents, warning about template overrides."""
        assert self.build_dir is not None
        for item in project_dir.iterdir():
            if item.name in template_files:
                self._log_template_override_warning(filename=item.name)

            if item.is_file():
                shutil.copy(src=item, dst=self.build_dir / item.name)
            elif item.is_dir():
                shutil.copytree(src=item, dst=self.build_dir / item.name, dirs_exist_ok=True)

    def _log_template_override_warning(self, filename: str) -> None:
        """Log warning about template file override."""
        logger.warning(f"Source file '{filename}' will override template file")

    def _build_docker_image(self) -> None:
        """Build Docker image."""
        logger.info(f"Building Docker image: {self.image_tag}")

        try:
            subprocess.run(["docker", "build", "-t", self.image_tag, str(self.build_dir)], check=True)
            logger.info(f"Docker image built successfully: {self.image_tag}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Docker build failed for image {self.image_tag}: {e}")
            raise ImageBuildError(f"Docker build failed: {e}")

    def _cleanup_if_needed(self) -> None:
        """Clean up build directory if temporary."""
        # Never cleanup if build_dir was specified by user
        if self.original_build_dir is not None:
            return

        if not self.build_dir:
            return

        # Safety check: never cleanup root directory
        if self.build_dir.resolve() == Path("/"):
            logger.error("Refusing to cleanup root directory")
            return

        # Only cleanup temporary directories (those created by tempfile.mkdtemp)
        if BUILD_DIR_PREFIX in self.build_dir.name:
            logger.info(f"Cleaning up temporary build directory: {self.build_dir}")
            shutil.rmtree(self.build_dir)

    def _save_build_info_file(self, project_path: str) -> None:
        """Save build information file."""
        assert self.build_dir is not None
        build_info = {"image_tag": self.image_tag, "project_path": project_path}
        info_file = self.build_dir / "build_info.json"
        with open(file=info_file, mode="w") as f:
            json.dump(obj=build_info, fp=f, indent=2)
