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
"""IAM client types for basic boto3 operations."""

from typing import Dict

from pydantic import BaseModel


class CreateRoleRequest(BaseModel):
    """Request for creating IAM role."""

    model_config = {"extra": "allow"}

    RoleName: str
    AssumeRolePolicyDocument: str
    Description: str | None = None


class CreateRoleResponse(BaseModel):
    """Response from creating IAM role."""

    model_config = {"extra": "allow"}

    Role: Dict[str, object]


class GetRoleResponse(BaseModel):
    """Response from getting IAM role."""

    model_config = {"extra": "allow"}

    Role: Dict[str, object]


class AttachRolePolicyRequest(BaseModel):
    """Request for attaching managed policy to role."""

    model_config = {"extra": "allow"}

    RoleName: str
    PolicyArn: str


class PutRolePolicyRequest(BaseModel):
    """Request for putting inline policy on role."""

    model_config = {"extra": "allow"}

    RoleName: str
    PolicyName: str
    PolicyDocument: str
