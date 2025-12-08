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
"""Core identity utilities for Nova Act CLI."""

from boto3 import Session
from botocore.exceptions import ClientError, NoCredentialsError

from nova_act.cli.core.error_detection import get_credential_error_message, is_credential_error
from nova_act.cli.core.exceptions import ConfigurationError


def validate_iam_role_arn(role_arn: str) -> bool:
    """Validate IAM role ARN format.

    Args:
        role_arn: The IAM role ARN to validate

    Returns:
        True if valid format, False otherwise
    """
    return role_arn.startswith("arn:aws:iam::") and ":role/" in role_arn


def extract_role_name_from_arn(role_arn: str) -> str:
    """Extract role name from IAM role ARN.

    Args:
        role_arn: The IAM role ARN (e.g., arn:aws:iam::123456789012:role/MyRole)

    Returns:
        The role name (e.g., MyRole)

    Raises:
        ValueError: If ARN format is invalid
    """
    if not validate_iam_role_arn(role_arn):
        raise ValueError(f"Invalid IAM role ARN format: {role_arn}")

    return role_arn.split(":role/")[1]


def auto_detect_account_id(session: Session | None, region: str) -> str:
    """Auto-detect AWS account ID using STS."""
    try:
        effective_session = session or Session()
        sts_client = effective_session.client("sts", region_name=region)
        response = sts_client.get_caller_identity()
        return str(response["Account"])
    except (NoCredentialsError, ClientError) as e:
        if is_credential_error(e):
            raise ConfigurationError(get_credential_error_message())
        raise
