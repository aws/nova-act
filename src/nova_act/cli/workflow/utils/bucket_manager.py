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
"""High-level S3 bucket management for Nova Act workflows."""

import logging

from boto3 import Session

from nova_act.cli.core.clients.s3.client import S3Client

logger = logging.getLogger(__name__)


class BucketManager:
    """Manages S3 bucket operations for Nova Act workflows."""

    def __init__(self, session: Session | None, region: str, account_id: str):
        self.region = region
        self.account_id = account_id
        self.s3_client = S3Client(session=session, region=region)

    def _default_bucket_exists(self) -> bool:
        """Check if default bucket exists directly."""
        bucket_name = self.generate_default_nova_act_bucket_name()
        return self.s3_client.bucket_exists(bucket_name)

    def ensure_default_bucket(self) -> str:
        """Ensure default S3 bucket exists, create if needed."""
        if self._default_bucket_exists():
            return self.generate_default_nova_act_bucket_name()
        return self._create_default_bucket()

    def _create_default_bucket(self) -> str:
        """Create default bucket with standard naming."""
        bucket_name = self.generate_default_nova_act_bucket_name()
        self.s3_client.create_bucket(bucket_name)
        return bucket_name

    def generate_default_nova_act_bucket_name(self) -> str:
        """Generate standard bucket name."""
        return f"nova-act-{self.account_id}-{self.region}"
