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
        if self.region == "us-east-1":
            self.client.create_bucket(Bucket=bucket_name)
        else:
            self.client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": self.region},  # type: ignore[typeddict-item]
            )

        try:
            self._block_public_access(bucket_name)
            self._enable_encryption(bucket_name)
            self._enable_versioning(bucket_name)
        except ClientError as e:
            logger.warning(f"Created bucket {bucket_name} but failed to apply security configurations: {e}")
        else:
            logger.info(f"Created secure S3 bucket: {bucket_name}")

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

    def upload_file(self, bucket: str, key: str, file_path: str) -> None:
        """Upload a file to S3."""
        logger.info(f"Uploading {file_path} to s3://{bucket}/{key}")
        self.client.upload_file(Filename=file_path, Bucket=bucket, Key=key)
        logger.info(f"Upload complete: s3://{bucket}/{key}")
