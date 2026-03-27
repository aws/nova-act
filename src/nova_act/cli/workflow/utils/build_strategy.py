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
"""Image build strategy abstraction for local and remote builds."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from boto3 import Session

from nova_act.cli.core.clients.ecr.client import ECRClient
from nova_act.cli.workflow.utils.docker_builder import DockerBuilder


@dataclass
class ImageBuildResult:
    """Result of an image build and push operation."""

    image_uri: str


class ImageBuilder(ABC):
    """Abstract base class for image build strategies."""

    @abstractmethod
    def build_and_push(self, build_dir: Path, image_tag: str, agent_name: str) -> ImageBuildResult:
        """Build a container image and push it to ECR.

        Args:
            build_dir: Directory containing build context (Dockerfile + project files).
            image_tag: Local image tag for the build.
            agent_name: Agent name used to generate ECR tag.

        Returns:
            ImageBuildResult with the full ECR image URI.
        """


class LocalImageBuilder(ImageBuilder):
    """Builds images locally using Docker and pushes to ECR."""

    def __init__(self, session: Session | None, region: str):
        self.session = session
        self.region = region

    def build_and_push(self, build_dir: Path, image_tag: str, agent_name: str) -> ImageBuildResult:
        """Build image locally with Docker, then push to ECR."""
        builder = DockerBuilder(image_tag=image_tag, build_dir=build_dir, force=True)
        builder.build_docker_image()

        ecr_client = ECRClient(session=self.session, region=self.region)
        ecr_uri = ecr_client.ensure_default_repository()
        ecr_tag = ecr_client.generate_unique_tag(agent_name)
        full_uri = ecr_client.push_image(local_image_tag=image_tag, ecr_uri=ecr_uri, target_tag=ecr_tag)

        return ImageBuildResult(image_uri=full_uri)
