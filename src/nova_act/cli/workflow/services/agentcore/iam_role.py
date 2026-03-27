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
"""AgentCore-specific IAM role creation and management."""

import json
import time
from typing import Dict

from boto3 import Session

from nova_act.cli.core.clients.iam.client import IAMClient
from nova_act.cli.core.clients.iam.types import (
    CreateRoleRequest,
    PutRolePolicyRequest,
)


class AgentCoreRoleCreator:
    """Creates and manages IAM roles for AgentCore workflows."""

    def __init__(self, session: Session | None, account_id: str, region: str):
        self.account_id = account_id
        self.region = region
        self.iam_client = IAMClient(session=session, region=region)

    def create_default_execution_role(self, workflow_name: str) -> str:
        """Create or return existing default execution role for workflow."""
        role_name = f"nova-act-{workflow_name}-role"
        role_arn = f"arn:aws:iam::{self.account_id}:role/{role_name}"

        if self.iam_client.role_exists(role_name=role_name):
            print(f"Using existing IAM role: {role_arn}")
            self._reconcile_role_policies(role_name)
            return role_arn

        return self._create_role_with_policies(role_name=role_name, workflow_name=workflow_name)

    def _reconcile_role_policies(self, role_name: str) -> None:
        """Update trust policy and re-apply all inline policies on an existing role."""
        trust_policy = self._build_trust_policy()

        current_role = self.iam_client.get_role(role_name)
        current_trust = current_role.Role.get("AssumeRolePolicyDocument", {})
        trust_changed = json.dumps(current_trust, sort_keys=True) != json.dumps(trust_policy, sort_keys=True)

        if trust_changed:
            self.iam_client.update_assume_role_policy(
                role_name=role_name,
                policy_document=json.dumps(trust_policy),
            )
            print("Updated trust policy. Waiting for IAM propagation...")
            time.sleep(10)

        self._attach_inline_policies(role_name)

    def _create_role_with_policies(self, role_name: str, workflow_name: str) -> str:
        """Create IAM role with required policies for AgentCore."""
        trust_policy = self._build_trust_policy()

        create_request = CreateRoleRequest(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description=f"Execution role for Nova Act workflow: {workflow_name}",
        )

        response = self.iam_client.create_role(create_request)
        role_arn = str(response.Role["Arn"])
        print(f"Created IAM role: {role_arn}")

        self._attach_inline_policies(role_name)

        print(f"Attached all required permissions to role: {role_arn}")
        print("Waiting for IAM role to propagate...")
        time.sleep(10)

        return role_arn

    def _build_trust_policy(self) -> Dict[str, object]:
        """Build trust policy for AgentCore and CodeBuild services."""
        return {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AssumeRolePolicy",
                    "Effect": "Allow",
                    "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                    "Condition": {
                        "StringEquals": {"aws:SourceAccount": self.account_id},
                        "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:*"},
                    },
                },
                {
                    "Sid": "CodeBuildAssumeRolePolicy",
                    "Effect": "Allow",
                    "Principal": {"Service": "codebuild.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                    "Condition": {
                        "StringEquals": {"aws:SourceAccount": self.account_id},
                        "ArnLike": {
                            "aws:SourceArn": f"arn:aws:codebuild:{self.region}:{self.account_id}:project/nova-act-*"
                        },
                    },
                },
            ],
        }

    def _attach_inline_policies(self, role_name: str) -> None:
        """Attach inline policies to role."""
        policies = self._get_inline_policies()

        for policy_name, policy_document in policies.items():
            request = PutRolePolicyRequest(
                RoleName=role_name,
                PolicyName=policy_name,
                PolicyDocument=json.dumps(policy_document),
            )
            self.iam_client.put_role_policy(request)

    def _get_inline_policies(self) -> Dict[str, Dict[str, object]]:
        """Get all inline policy definitions."""
        return {
            "ECRAccessPolicy": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["ecr:GetAuthorizationToken"],
                        "Resource": "*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "ecr:BatchGetImage",
                            "ecr:GetDownloadUrlForLayer",
                            "ecr:BatchCheckLayerAvailability",
                            "ecr:CompleteLayerUpload",
                            "ecr:InitiateLayerUpload",
                            "ecr:PutImage",
                            "ecr:UploadLayerPart",
                        ],
                        "Resource": f"arn:aws:ecr:{self.region}:{self.account_id}:repository/nova-act-*",
                    },
                ],
            },
            "CodeBuildPolicy": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "codebuild:StartBuild",
                            "codebuild:BatchGetBuilds",
                        ],
                        "Resource": f"arn:aws:codebuild:{self.region}:{self.account_id}:project/nova-act-*",
                    }
                ],
            },
            "CloudWatchLogsPolicy": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                            "logs:DescribeLogStreams",
                            "logs:DescribeLogGroups",
                        ],
                        "Resource": "*",
                    }
                ],
            },
            "XRayPolicy": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "xray:PutTraceSegments",
                            "xray:PutTelemetryRecords",
                            "xray:GetSamplingRules",
                            "xray:GetSamplingTargets",
                        ],
                        "Resource": "*",
                    }
                ],
            },
            "CloudWatchMetricsPolicy": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["cloudwatch:PutMetricData"],
                        "Resource": "*",
                        "Condition": {"StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}},
                    }
                ],
            },
            "BedrockAgentCorePolicy": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "bedrock-agentcore:GetBrowserSession",
                            "bedrock-agentcore:StartBrowserSession",
                            "bedrock-agentcore:StopBrowserSession",
                            "bedrock-agentcore:UpdateBrowserStream",
                            "bedrock-agentcore:DeleteBrowser",
                            "bedrock-agentcore:GetBrowser",
                            "bedrock-agentcore:ConnectBrowserAutomationStream",
                            "bedrock-agentcore:ListBrowsers",
                            "bedrock-agentcore:ListBrowserSessions",
                            "bedrock-agentcore:CreateBrowser",
                            "bedrock-agentcore:ConnectBrowserLiveViewStream",
                        ],
                        "Resource": "*",
                    }
                ],
            },
            "S3AccessPolicy": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
                        "Resource": "arn:aws:s3:::nova-act-*/*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:ListBucket",
                            "s3:CreateBucket",
                            "s3:GetBucketLocation",
                            "s3:HeadBucket",
                            "s3:PutBucketPublicAccessBlock",
                            "s3:GetBucketPublicAccessBlock",
                            "s3:PutBucketEncryption",
                            "s3:GetBucketEncryption",
                            "s3:PutBucketVersioning",
                            "s3:GetBucketVersioning",
                        ],
                        "Resource": "arn:aws:s3:::nova-act-*",
                    },
                    {"Effect": "Allow", "Action": ["s3:ListAllMyBuckets"], "Resource": "*"},
                ],
            },
            "NovaActPolicy": {
                "Version": "2012-10-17",
                "Statement": [{"Effect": "Allow", "Action": ["nova-act:*"], "Resource": ["*"]}],
            },
        }
