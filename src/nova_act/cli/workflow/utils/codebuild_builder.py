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
"""CodeBuild-based image builder for remote ARM64 Docker builds."""

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any

from boto3 import Session

from nova_act.cli.core.clients.codebuild.client import CodeBuildClient
from nova_act.cli.core.clients.codebuild.constants import (
    CODEBUILD_COMPUTE_TYPE,
    CODEBUILD_ENV_TYPE,
    CODEBUILD_IMAGE,
    CODEBUILD_PROJECT_PREFIX,
)
from nova_act.cli.core.clients.ecr.client import ECRClient
from nova_act.cli.core.clients.s3.client import S3Client
from nova_act.cli.workflow.utils.bucket_manager import BucketManager
from nova_act.cli.workflow.utils.build_strategy import ImageBuilder, ImageBuildResult

logger = logging.getLogger(__name__)

BUILDSPEC = """\
version: 0.2
phases:
  pre_build:
    commands:
      - echo Logging in to Amazon ECR...
      - >-
        aws ecr get-login-password --region $AWS_DEFAULT_REGION |
        docker login --username AWS --password-stdin $ECR_REGISTRY
  build:
    commands:
      - echo Building Docker image...
      - docker build --platform linux/arm64 -t $IMAGE_TAG .
      - docker tag $IMAGE_TAG $FULL_IMAGE_URI
  post_build:
    commands:
      - echo Pushing image to ECR...
      - docker push $FULL_IMAGE_URI
      - echo Build and push completed
"""


class CodeBuildImageBuilder(ImageBuilder):
    """Builds images remotely using AWS CodeBuild on ARM64 instances."""

    def __init__(self, session: Session | None, region: str, account_id: str, role_arn: str):
        self.session = session
        self.region = region
        self.account_id = account_id
        self.role_arn = role_arn
        self.codebuild_client = CodeBuildClient(session=session, region=region)
        self.s3_client = S3Client(session=session, region=region)
        self.bucket_manager = BucketManager(session=session, region=region, account_id=account_id)

    def build_and_push(self, build_dir: Path, image_tag: str, agent_name: str) -> ImageBuildResult:
        """Build image remotely via CodeBuild and push to ECR."""
        ecr_client = ECRClient(session=self.session, region=self.region)
        ecr_uri = ecr_client.ensure_default_repository()
        ecr_tag = ecr_client.generate_unique_tag(agent_name)
        full_image_uri = f"{ecr_uri}:{ecr_tag}"
        ecr_registry = ecr_uri.split("/")[0]

        # 1. Upload build context to S3
        bucket = self.bucket_manager.ensure_default_bucket()
        s3_key = f"codebuild-sources/{image_tag.replace(':', '-')}.zip"
        zip_path = self._zip_build_context(build_dir)

        try:
            self.s3_client.upload_file(bucket=bucket, key=s3_key, file_path=str(zip_path))
        finally:
            shutil.rmtree(zip_path.parent, ignore_errors=True)

        # 2. Ensure CodeBuild project
        project_name = f"{CODEBUILD_PROJECT_PREFIX}-{self.region}"
        self._ensure_codebuild_project(project_name)

        # 3. Start build with env vars
        s3_location = f"{bucket}/{s3_key}"
        env_vars = self._build_env_vars(ecr_registry, image_tag, full_image_uri)
        build_id = self.codebuild_client.start_build(
            project_name=project_name,
            source_s3_location=s3_location,
            env_vars=env_vars,
        )

        # 4. Poll until complete
        logger.info(f"Waiting for CodeBuild build to complete: {build_id}")
        self.codebuild_client.poll_build(build_id)

        return ImageBuildResult(image_uri=full_image_uri)

    def _zip_build_context(self, build_dir: Path) -> Path:
        """Zip build directory contents for S3 upload."""
        tmp_dir = Path(tempfile.mkdtemp())
        zip_base = tmp_dir / "build_context"
        shutil.make_archive(str(zip_base), "zip", str(build_dir))
        zip_path = zip_base.with_suffix(".zip")
        logger.info(f"Created build context archive: {zip_path}")
        return zip_path

    def _ensure_codebuild_project(self, project_name: str) -> None:
        """Create CodeBuild project if it doesn't exist, or reconcile config if stale."""
        existing = self.codebuild_client.get_project(project_name)
        if existing:
            update_kwargs: dict[str, Any] = {}  # type: ignore[explicit-any]

            # Reconcile service role
            if existing.get("serviceRole", "") != self.role_arn:
                update_kwargs["service_role_arn"] = self.role_arn

            # Reconcile environment config
            expected_env = {
                "type": CODEBUILD_ENV_TYPE,
                "image": CODEBUILD_IMAGE,
                "computeType": CODEBUILD_COMPUTE_TYPE,
                "privilegedMode": True,
            }
            existing_env = existing.get("environment", {})
            if any(existing_env.get(k) != v for k, v in expected_env.items()):
                update_kwargs["environment"] = expected_env

            if update_kwargs:
                logger.info(f"Reconciling CodeBuild project config ({', '.join(update_kwargs)}): {project_name}")
                self.codebuild_client.update_project(project_name, **update_kwargs)
            else:
                logger.info(f"Using existing CodeBuild project: {project_name}")
            return

        logger.info(f"Creating CodeBuild project: {project_name}")
        self.codebuild_client.create_project(
            project_name=project_name,
            service_role_arn=self.role_arn,
            buildspec=BUILDSPEC,
        )

    def _build_env_vars(self, ecr_registry: str, image_tag: str, full_image_uri: str) -> list[dict[str, str]]:
        """Build environment variable overrides for CodeBuild."""
        return [
            {"name": "ECR_REGISTRY", "value": ecr_registry, "type": "PLAINTEXT"},
            {"name": "IMAGE_TAG", "value": image_tag, "type": "PLAINTEXT"},
            {"name": "FULL_IMAGE_URI", "value": full_image_uri, "type": "PLAINTEXT"},
            {"name": "AWS_DEFAULT_REGION", "value": self.region, "type": "PLAINTEXT"},
        ]
