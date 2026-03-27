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
"""Shared error handlers for workflow commands."""

from botocore.exceptions import ClientError

from nova_act.cli.core.error_detection import (
    extract_operation_name,
    extract_permission_from_error,
    get_credential_error_message,
    get_permission_error_message,
    is_permission_error,
)
from nova_act.cli.core.styling import styled_error_exception


def handle_credential_error() -> None:
    """Handle AWS credential errors."""
    raise styled_error_exception(get_credential_error_message())


def handle_client_error(error: ClientError, workflow_name: str, region: str, account_id: str, context: str) -> None:
    """Handle AWS ClientError with permission detection.

    Args:
        error: The ClientError from AWS.
        workflow_name: Name of the workflow being operated on.
        region: AWS region.
        account_id: AWS account ID.
        context: Description of the operation for the fallback error message (e.g. "deployment").
    """
    if is_permission_error(error):
        operation = extract_operation_name(error)
        permission = extract_permission_from_error(error)
        message = get_permission_error_message(
            operation=operation,
            workflow_name=workflow_name,
            region=region,
            account_id=account_id,
            permission=permission,
        )
        raise styled_error_exception(message)
    raise styled_error_exception(f"AWS error during {context}: {str(error)}")
