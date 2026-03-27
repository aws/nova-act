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
"""Constants for CodeBuild client."""

CODEBUILD_SERVICE = "codebuild"
CODEBUILD_PROJECT_PREFIX = "nova-act-build"
CODEBUILD_COMPUTE_TYPE = "BUILD_GENERAL1_MEDIUM"
CODEBUILD_IMAGE = "aws/codebuild/amazonlinux-aarch64-standard:3.0"
CODEBUILD_ENV_TYPE = "ARM_CONTAINER"
CODEBUILD_TIMEOUT_MINUTES = 30
CODEBUILD_POLL_INTERVAL_SECONDS = 10

# Build status values
CODEBUILD_STATUS_SUCCEEDED = "SUCCEEDED"
CODEBUILD_STATUS_FAILED = "FAILED"
CODEBUILD_STATUS_FAULT = "FAULT"
CODEBUILD_STATUS_STOPPED = "STOPPED"
CODEBUILD_STATUS_TIMED_OUT = "TIMED_OUT"
CODEBUILD_TERMINAL_FAILURE_STATUSES = frozenset(
    {CODEBUILD_STATUS_FAILED, CODEBUILD_STATUS_FAULT, CODEBUILD_STATUS_STOPPED, CODEBUILD_STATUS_TIMED_OUT}
)
