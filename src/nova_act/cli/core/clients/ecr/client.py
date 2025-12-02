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
"""ECR client for repository and image operations."""

import base64
import logging
import re
import subprocess
import time

from boto3 import Session
from botocore.exceptions import ClientError

from nova_act.cli.core.clients.ecr.constants import (
    DEFAULT_ECR_REPO_NAME,
    ECR_SERVICE,
)
from nova_act.cli.core.exceptions import ImageBuildError

logger = logging.getLogger(__name__)


class ECRClient:
    """Client for ECR repository and image operations."""

    def __init__(self, session: Session | None, region: str):
        self.region = region
        self.session = session or Session()
        self.ecr_client = self.session.client(ECR_SERVICE, region_name=region)  # type: ignore

    def generate_unique_tag(self, tag_name: str) -> str:
        """Generate unique tag with timestamp for multi-user safety."""
        clean_name = self._sanitize_tag_name(tag_name)
        timestamp = int(time.time())
        return f"{clean_name}-{timestamp}"

    def _sanitize_tag_name(self, tag_name: str) -> str:
        """Sanitize tag name for ECR tag requirements."""
        original_name = tag_name
        clean_name = re.sub(pattern=r"[^a-zA-Z0-9_.-]", repl="-", string=tag_name)[:117]
        clean_name = clean_name.strip(".-") or "workflow"

        if clean_name != original_name:
            logger.warning(msg=f"Tag name sanitized for ECR: '{original_name}' -> '{clean_name}'")

        return clean_name

    def check_repository_exists(self, ecr_uri: str) -> bool:
        """Check if ECR repository exists."""
        try:
            repo_name = ecr_uri.split("/")[-1].split(":")[0]
            self.ecr_client.describe_repositories(repositoryNames=[repo_name])
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "RepositoryNotFoundException":
                return False
            raise ImageBuildError(f"Failed to check repository existence: {e}")

    def _ensure_default_repository(self) -> str:
        """Ensure default repository exists."""
        try:
            response = self.ecr_client.describe_repositories(repositoryNames=[DEFAULT_ECR_REPO_NAME])
            repo_uri = str(response["repositories"][0]["repositoryUri"])
            logger.info(f"Using existing ECR repository: {repo_uri}")
            return repo_uri
        except ClientError as e:
            if e.response["Error"]["Code"] == "RepositoryNotFoundException":
                return self._create_default_repository(DEFAULT_ECR_REPO_NAME)
            raise ImageBuildError(f"Failed to check ECR repository: {e}")

    def _create_default_repository(self, repository_name: str) -> str:
        """Create default ECR repository."""
        try:
            logger.info(f"Creating ECR repository: {repository_name}")
            response = self.ecr_client.create_repository(repositoryName=repository_name)
            repo_uri = str(response["repository"]["repositoryUri"])
            logger.info(f"Created ECR repository: {repo_uri}")
            return repo_uri
        except ClientError as e:
            raise ImageBuildError(f"Failed to create ECR repository: {e}")

    def push_image(self, local_image_tag: str, ecr_uri: str, target_tag: str) -> str:
        """Push image with specific tag, return full ECR image URI."""
        full_ecr_uri = self.build_image_uri(ecr_uri=ecr_uri, tag=target_tag)

        self._login_to_ecr()
        self._tag_image(local_image_tag=local_image_tag, full_ecr_uri=full_ecr_uri)
        self._push_image(full_ecr_uri=full_ecr_uri)
        self._log_push_success(full_ecr_uri=full_ecr_uri)

        return full_ecr_uri

    def _login_to_ecr(self) -> None:
        """Login to ECR registry."""
        try:
            token_response = self.ecr_client.get_authorization_token()
            token = token_response["authorizationData"][0]["authorizationToken"]
            endpoint = token_response["authorizationData"][0]["proxyEndpoint"]

            username, password = base64.b64decode(token).decode().split(":")
            subprocess.run(
                ["docker", "login", "--username", username, "--password-stdin", endpoint],
                input=password,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise ImageBuildError(f"ECR login failed: {e}")

    def _tag_image(self, local_image_tag: str, full_ecr_uri: str) -> None:
        """Tag local image for ECR."""
        try:
            subprocess.run(args=["docker", "tag", local_image_tag, full_ecr_uri], check=True)
        except subprocess.CalledProcessError as e:
            raise ImageBuildError(f"Docker tag failed: {e}")

    def _push_image(self, full_ecr_uri: str) -> None:
        """Push tagged image to ECR."""
        try:
            subprocess.run(args=["docker", "push", full_ecr_uri], check=True)
        except subprocess.CalledProcessError as e:
            raise ImageBuildError(f"Docker push failed: {e}")

    def build_image_uri(self, ecr_uri: str, tag: str) -> str:
        """Build complete image URI from ECR URI and tag."""
        return f"{ecr_uri}:{tag}"

    def _log_push_success(self, full_ecr_uri: str) -> None:
        """Log successful image push."""
        logger.info(f"Pushed image to ECR: {full_ecr_uri}")
