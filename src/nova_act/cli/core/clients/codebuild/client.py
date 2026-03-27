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
"""CodeBuild client for remote container image builds."""

import logging
import time
from typing import Any

from boto3 import Session
from botocore.exceptions import ClientError

from nova_act.cli.core.clients.codebuild.constants import (
    CODEBUILD_COMPUTE_TYPE,
    CODEBUILD_ENV_TYPE,
    CODEBUILD_IMAGE,
    CODEBUILD_POLL_INTERVAL_SECONDS,
    CODEBUILD_SERVICE,
    CODEBUILD_STATUS_SUCCEEDED,
    CODEBUILD_TERMINAL_FAILURE_STATUSES,
    CODEBUILD_TIMEOUT_MINUTES,
)
from nova_act.cli.core.exceptions import CodeBuildError

logger = logging.getLogger(__name__)


class CodeBuildClient:
    """Client for AWS CodeBuild operations."""

    def __init__(self, session: Session | None, region: str):
        self.region = region
        self.session = session or Session()
        self.client = self.session.client(CODEBUILD_SERVICE, region_name=region)  # type: ignore

    def get_project(self, project_name: str) -> dict[str, Any] | None:  # type: ignore[explicit-any]
        """Get a CodeBuild project, or None if it doesn't exist."""
        try:
            response = self.client.batch_get_projects(names=[project_name])
            projects = response.get("projects", [])
            return dict(projects[0]) if projects else None
        except ClientError as e:
            raise CodeBuildError(f"Failed to get CodeBuild project: {e}") from e

    def project_exists(self, project_name: str) -> bool:
        """Check if a CodeBuild project exists."""
        return self.get_project(project_name) is not None

    def update_project(  # type: ignore[explicit-any]
        self,
        project_name: str,
        service_role_arn: str | None = None,
        environment: dict[str, Any] | None = None,
    ) -> None:
        """Update an existing CodeBuild project's configuration."""
        try:
            kwargs: dict[str, Any] = {"name": project_name}  # type: ignore[explicit-any]
            if service_role_arn:
                kwargs["serviceRole"] = service_role_arn
            if environment:
                kwargs["environment"] = environment
            self.client.update_project(**kwargs)
            logger.info(f"Updated CodeBuild project: {project_name}")
        except ClientError as e:
            raise CodeBuildError(f"Failed to update CodeBuild project: {e}") from e

    def create_project(
        self,
        project_name: str,
        service_role_arn: str,
        buildspec: str,
    ) -> None:
        """Create a CodeBuild project configured for ARM64 Docker builds."""
        try:
            self.client.create_project(
                name=project_name,
                # Placeholder source — start_build() overrides this via sourceLocationOverride
                source={"type": "S3", "location": "placeholder/placeholder.zip", "buildspec": buildspec},
                artifacts={"type": "NO_ARTIFACTS"},
                environment={
                    "type": CODEBUILD_ENV_TYPE,
                    "image": CODEBUILD_IMAGE,
                    "computeType": CODEBUILD_COMPUTE_TYPE,
                    "privilegedMode": True,
                },
                serviceRole=service_role_arn,
                timeoutInMinutes=CODEBUILD_TIMEOUT_MINUTES,
            )
            logger.info(f"Created CodeBuild project: {project_name}")
        except ClientError as e:
            raise CodeBuildError(f"Failed to create CodeBuild project: {e}") from e

    def start_build(
        self,
        project_name: str,
        source_s3_location: str,
        env_vars: list[dict[str, str]] | None = None,
    ) -> str:
        """Start a CodeBuild build and return the build ID."""
        try:
            params: dict[str, Any] = {  # type: ignore[explicit-any]
                "projectName": project_name,
                "sourceLocationOverride": source_s3_location,
                "sourceTypeOverride": "S3",
            }
            if env_vars:
                params["environmentVariablesOverride"] = env_vars

            response = self.client.start_build(**params)
            build_id = str(response["build"]["id"])
            logger.info(f"Started CodeBuild build: {build_id}")
            return build_id
        except ClientError as e:
            raise CodeBuildError(f"Failed to start CodeBuild build: {e}") from e

    def get_build(self, build_id: str) -> dict[str, Any]:  # type: ignore[explicit-any]
        """Get build status and details."""
        try:
            response = self.client.batch_get_builds(ids=[build_id])
            builds = response.get("builds", [])
            if not builds:
                raise CodeBuildError(f"Build not found: {build_id}")
            return dict(builds[0])
        except ClientError as e:
            raise CodeBuildError(f"Failed to get build status: {e}") from e

    def poll_build(self, build_id: str, timeout: int = CODEBUILD_TIMEOUT_MINUTES * 60) -> None:
        """Poll build until completion or timeout."""
        start_time = time.time()

        while True:
            build = self.get_build(build_id)
            status = build.get("buildStatus", "UNKNOWN")

            match status:
                case s if s == CODEBUILD_STATUS_SUCCEEDED:
                    logger.info(f"Build succeeded: {build_id}")
                    return
                case s if s in CODEBUILD_TERMINAL_FAILURE_STATUSES:
                    phase_details = self._extract_failure_details(build)
                    raise CodeBuildError(f"Build {status}: {build_id}. {phase_details}")

            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise CodeBuildError(f"Build timed out after {timeout}s: {build_id}")

            logger.info(f"Build in progress ({status})... [{int(elapsed)}s elapsed]")
            time.sleep(CODEBUILD_POLL_INTERVAL_SECONDS)

    def _extract_failure_details(self, build: dict[str, Any]) -> str:  # type: ignore[explicit-any]
        """Extract failure details from build phases and CloudWatch logs."""
        details = []

        # Phase context messages
        phases = build.get("phases", [])
        for phase in reversed(phases):
            contexts = phase.get("contexts", [])
            for ctx in contexts:
                message = ctx.get("message", "")
                if message:
                    details.append(f"Phase {phase.get('phaseType', 'UNKNOWN')}: {message}")
                    break
            if details:
                break

        # Tail of CloudWatch build logs
        try:
            logs_info = build.get("logs", {})
            group = logs_info.get("groupName")
            stream = logs_info.get("streamName")
            if group and stream:
                logs_client = self.session.client("logs", region_name=self.region)
                response = logs_client.get_log_events(
                    logGroupName=group, logStreamName=stream, startFromHead=False, limit=20
                )
                log_lines = [e.get("message", "").rstrip() for e in response.get("events", [])]
                if log_lines:
                    details.append("Build log tail:\n" + "\n".join(log_lines))
        except Exception:
            logger.debug("Could not retrieve CloudWatch build logs", exc_info=True)

        return "\n".join(details) if details else "No detailed error information available"
