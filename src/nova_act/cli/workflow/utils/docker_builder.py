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

import fnmatch
import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Set

from nova_act.cli.core.constants import BUILD_DIR_PREFIX
from nova_act.cli.core.exceptions import ImageBuildError

logger = logging.getLogger(__name__)

# Directories excluded from project copy during Docker build.
# These are universally safe to exclude: version control, caches, virtual envs, and secrets.
DEFAULT_EXCLUDE_DIRS: Set[str] = {
    ".git",
    "__pycache__",
    "node_modules",
    ".env",
    ".venv",
    "venv",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
}

# File patterns excluded from project copy during Docker build.
DEFAULT_EXCLUDE_FILE_PATTERNS: Set[str] = {"*.pyc", "*.pyo"}


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
            self.build_dir = self.ensure_build_directory()
            logger.info(f"Build context directory: {self.build_dir}")

            self.prepare_build_dir(project_path=project_path, template_dir=template_dir)
            self.build_docker_image()

            if self.original_build_dir is not None:
                self.save_build_info_file(project_path)
                logger.info(f"Build artifacts preserved in: {self.build_dir}")

            logger.info(f"Docker build completed successfully: {self.image_tag}")
            return self.image_tag
        finally:
            self._cleanup_if_needed()

    def ensure_build_directory(self) -> Path:
        """Create build directory."""
        if self.build_dir:
            if self.build_dir.exists() and not self.force:
                raise ImageBuildError(f"Build directory exists: {self.build_dir}")
            self.build_dir.mkdir(parents=True, exist_ok=True)
            return self.build_dir
        return Path(tempfile.mkdtemp(prefix=BUILD_DIR_PREFIX))

    def prepare_build_dir(self, project_path: str, template_dir: Path) -> None:
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
            logger.warning(f"Source file '{project_file.name}' will override template file")
        shutil.copy(src=project_file, dst=self.build_dir / project_file.name)

    @staticmethod
    def _should_exclude(name: str, is_dir: bool) -> bool:
        """Check if a file or directory should be excluded from project copy."""
        if is_dir:
            return name in DEFAULT_EXCLUDE_DIRS
        return any(fnmatch.fnmatch(name, pattern) for pattern in DEFAULT_EXCLUDE_FILE_PATTERNS)

    @staticmethod
    def _make_copytree_ignore() -> Callable[[str, list[str]], set[str]]:
        """Create an ignore function for shutil.copytree that filters excluded patterns."""

        def _ignore(directory: str, contents: list[str]) -> set[str]:
            ignored: set[str] = set()
            dir_path = Path(directory)
            for name in contents:
                is_dir = (dir_path / name).is_dir()
                if DockerBuilder._should_exclude(name, is_dir):
                    ignored.add(name)
            return ignored

        return _ignore

    def _copy_directory_contents(self, project_dir: Path, template_files: Set[str]) -> None:
        """Copy directory contents, excluding problematic dirs/files and warning about template overrides."""
        assert self.build_dir is not None
        ignore_fn = self._make_copytree_ignore()

        for item in project_dir.iterdir():
            if self._should_exclude(item.name, item.is_dir()):
                logger.info(f"Excluding '{item.name}' from project copy")
                continue

            if item.name in template_files:
                logger.warning(f"Source file '{item.name}' will override template file")

            if item.is_file():
                shutil.copy(src=item, dst=self.build_dir / item.name)
            elif item.is_dir():
                shutil.copytree(src=item, dst=self.build_dir / item.name, dirs_exist_ok=True, ignore=ignore_fn)

    def build_docker_image(self) -> None:
        """Build Docker image."""
        logger.info(f"Building Docker image: {self.image_tag}")

        try:
            subprocess.run(
                ["docker", "build", "--platform", "linux/arm64", "-t", self.image_tag, str(self.build_dir)],
                check=True,
            )  # nosec B607
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

    def save_build_info_file(self, project_path: str) -> None:
        """Save build information file."""
        assert self.build_dir is not None
        build_info = {"image_tag": self.image_tag, "project_path": project_path}
        info_file = self.build_dir / "build_info.json"
        with open(file=info_file, mode="w") as f:
            json.dump(obj=build_info, fp=f, indent=2)
