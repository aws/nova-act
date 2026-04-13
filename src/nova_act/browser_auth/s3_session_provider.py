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
"""S3-based browser session provider.

Persists browser storage state as a JSON blob in Amazon S3
with server-side encryption (SSE-KMS).
"""

from __future__ import annotations

import json
import logging

from mypy_boto3_s3 import S3Client
from playwright.sync_api import StorageState

from nova_act.browser_auth.browser_session_provider import BrowserSessionProvider
from nova_act.types.errors import BrowserAuthError

_LOGGER = logging.getLogger(__name__)


class S3SessionProvider(BrowserSessionProvider):
    """Browser session provider backed by Amazon S3.

    Stores the browser storage state (cookies and localStorage)
    as a JSON object in S3 with SSE-KMS encryption.
    Each profile maps to a single S3 object.

    Example:
        >>> from nova_act import NovaAct
        >>> from nova_act.browser_auth import S3SessionProvider
        >>>
        >>> provider = S3SessionProvider(
        ...     bucket="my-session-bucket",
        ...     profile="expense-agent",
        ...     kms_key_id="alias/my-key",
        ... )
        >>> with NovaAct(
        ...     starting_page="https://example.com",
        ...     browser_auth=provider,
        ... ) as nova:
        ...     nova.act("Do something")

    A customer managed KMS key (CMK) is recommended for session
    state encryption. This gives you control over the key policy,
    auditable key usage via CloudTrail, and the ability to revoke
    access to all stored sessions by disabling the key. Create one
    with::

        aws kms create-key --description "NovaAct session encryption"
        aws kms create-alias --alias-name alias/nova-act-sessions \\
            --target-key-id <key-id>

    Then pass ``kms_key_id="alias/nova-act-sessions"`` to this
    provider. When ``kms_key_id`` is ``None``, the bucket's default
    encryption settings are used instead.

    Args:
        bucket: S3 bucket name.
        profile: Session profile name. Used as part of the S3 key.
            Defaults to ``"default"``.
        key_prefix: S3 key prefix. Defaults to
            ``"nova-act-sessions/"``.
        kms_key_id: KMS key ID, ARN, or alias for SSE-KMS
            encryption. A customer managed key (CMK) is recommended.
            When ``None``, uses the bucket's default encryption.
        region: AWS region for the S3 client. Defaults to the
            boto3 default region.
    """

    def __init__(
        self,
        bucket: str,
        profile: str = "default",
        *,
        key_prefix: str = "nova-act-sessions/",
        kms_key_id: str | None = None,
        region: str | None = None,
    ) -> None:
        self._bucket = bucket
        self._profile = profile
        self._key_prefix = key_prefix
        self._kms_key_id = kms_key_id
        self._s3_key = f"{key_prefix}{profile}.json"
        self._client = self._make_s3_client(region)

    @property
    def name(self) -> str:
        return "S3SessionProvider"

    def load_storage_state(self) -> StorageState | None:
        """Load storage state from S3.

        Returns:
            The storage state dict, or ``None`` if the object
            does not exist.

        Raises:
            BrowserAuthError: If S3 is unreachable or the stored
                data is not valid JSON.
        """
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=self._s3_key)
            body = response["Body"].read().decode("utf-8")
            state: StorageState = json.loads(body)
            _LOGGER.info("Loaded session state from s3://%s/%s", self._bucket, self._s3_key)
            return state
        except self._client.exceptions.NoSuchKey:
            _LOGGER.debug("No saved session at s3://%s/%s", self._bucket, self._s3_key)
            return None
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise BrowserAuthError(f"Corrupted session data at s3://{self._bucket}/{self._s3_key}: {exc}") from exc
        except Exception as exc:
            raise BrowserAuthError(f"Failed to load session from s3://{self._bucket}/{self._s3_key}: {exc}") from exc

    def save_storage_state(self, state: StorageState) -> None:
        """Save storage state to S3 with SSE-KMS encryption.

        Raises:
            BrowserAuthError: If the state cannot be saved to S3.
        """
        try:
            body = json.dumps(state, default=str).encode("utf-8")
            if self._kms_key_id:
                self._client.put_object(
                    Bucket=self._bucket,
                    Key=self._s3_key,
                    Body=body,
                    ContentType="application/json",
                    ServerSideEncryption="aws:kms",
                    SSEKMSKeyId=self._kms_key_id,
                )
            else:
                self._client.put_object(
                    Bucket=self._bucket,
                    Key=self._s3_key,
                    Body=body,
                    ContentType="application/json",
                    ServerSideEncryption="aws:kms",
                )
            _LOGGER.info("Saved session state to s3://%s/%s", self._bucket, self._s3_key)
        except Exception as exc:
            raise BrowserAuthError(f"Failed to save session to s3://{self._bucket}/{self._s3_key}: {exc}") from exc

    @staticmethod
    def _make_s3_client(region: str | None) -> S3Client:
        """Create a boto3 S3 client."""
        import boto3

        if region:
            return boto3.client("s3", region_name=region)
        return boto3.client("s3")
