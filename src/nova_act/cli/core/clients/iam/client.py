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
"""IAM client for basic boto3 IAM operations."""

from boto3 import Session
from botocore.exceptions import ClientError

from nova_act.cli.core.clients.iam.types import (
    AttachRolePolicyRequest,
    CreateRoleRequest,
    CreateRoleResponse,
    GetRoleResponse,
    PutRolePolicyRequest,
)


class IAMClient:
    """Client for basic IAM operations."""

    def __init__(self, session: Session | None, region: str):
        self.region = region
        self.session = session or Session()
        self.client = self.session.client("iam", region_name=region)

    def create_role(self, request: CreateRoleRequest) -> CreateRoleResponse:
        """Create IAM role."""
        response = self.client.create_role(**request.model_dump())
        return CreateRoleResponse(**response)

    def get_role(self, role_name: str) -> GetRoleResponse:
        """Get IAM role."""
        response = self.client.get_role(RoleName=role_name)
        return GetRoleResponse(**response)

    def role_exists(self, role_name: str) -> bool:
        """Check if IAM role exists."""
        try:
            self.get_role(role_name)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchEntity":
                return False
            raise RuntimeError(f"Failed to check IAM role {role_name}: {e}")

    def attach_role_policy(self, request: AttachRolePolicyRequest) -> None:
        """Attach managed policy to role."""
        self.client.attach_role_policy(**request.model_dump())

    def put_role_policy(self, request: PutRolePolicyRequest) -> None:
        """Put inline policy on role."""
        self.client.put_role_policy(**request.model_dump())
