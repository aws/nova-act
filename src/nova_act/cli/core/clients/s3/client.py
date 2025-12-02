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
"""S3 client for bucket operations."""

import logging

from boto3 import Session
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class S3Client:
    """Client for S3 bucket operations."""

    def __init__(self, session: Session | None, region: str):
        self.region = region
        self.session = session or Session()
        self.client = self.session.client("s3", region_name=region)

    def bucket_exists(self, bucket_name: str) -> bool:
        """Check if bucket exists and is accessible."""
        try:
            self.client.head_bucket(Bucket=bucket_name)
            return True
        except ClientError:
            return False

    def get_bucket_location(self, bucket_name: str) -> str:
        """Get bucket region."""
        response = self.client.get_bucket_location(Bucket=bucket_name)
        region = response.get("LocationConstraint")
        return region or "us-east-1"

    def create_bucket(self, bucket_name: str) -> None:
        """Create S3 bucket with security configurations."""
        self._create_bucket_resource(bucket_name)
        self._configure_bucket_security(bucket_name)
        self._log_bucket_creation_success(bucket_name)

    def _log_bucket_creation_success(self, bucket_name: str) -> None:
        """Log successful bucket creation."""
        logger.info(f"Created secure S3 bucket: {bucket_name}")

    def _create_bucket_resource(self, bucket_name: str) -> None:
        """Create the S3 bucket resource."""
        if self.region == "us-east-1":
            self.client.create_bucket(Bucket=bucket_name)
        else:
            self.client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": self.region},  # type: ignore[typeddict-item]
            )

    def _configure_bucket_security(self, bucket_name: str) -> None:
        """Configure bucket security settings."""
        try:
            self._apply_security_configurations(bucket_name)
            self._log_security_success(bucket_name)
        except ClientError as e:
            self._log_security_failure(bucket_name=bucket_name, error=e)

    def _apply_security_configurations(self, bucket_name: str) -> None:
        """Apply all security configurations to bucket."""
        self._block_public_access(bucket_name)
        self._enable_encryption(bucket_name)
        self._enable_versioning(bucket_name)

    def _log_security_success(self, bucket_name: str) -> None:
        """Log successful security configuration."""
        logger.info(f"Applied security configurations to bucket: {bucket_name}")

    def _log_security_failure(self, bucket_name: str, error: ClientError) -> None:
        """Log security configuration failure."""
        logger.warning(f"Failed to apply security configurations to {bucket_name}: {error}")

    def _block_public_access(self, bucket_name: str) -> None:
        """Block all public access to the bucket."""
        self.client.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )

    def _enable_encryption(self, bucket_name: str) -> None:
        """Enable server-side encryption for the bucket."""
        self.client.put_bucket_encryption(
            Bucket=bucket_name,
            ServerSideEncryptionConfiguration={
                "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
            },
        )

    def _enable_versioning(self, bucket_name: str) -> None:
        """Enable versioning for the bucket."""
        self.client.put_bucket_versioning(Bucket=bucket_name, VersioningConfiguration={"Status": "Enabled"})
