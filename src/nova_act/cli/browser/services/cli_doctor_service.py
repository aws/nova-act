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
"""CLIDoctorService: business logic for all doctor diagnostic checks."""

import logging
import os
from dataclasses import dataclass

import yaml

from nova_act.cli.browser.services.session.chrome_launcher import ChromeLauncher
from nova_act.cli.browser.services.session.manager import SessionManager
from nova_act.cli.browser.utils.auth import has_aws_credentials
from nova_act.cli.core.config import get_session_dir, read_config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CheckResult:
    """Result of a single doctor check."""

    name: str
    status: str
    message: str
    fix: str | None = None


class CLIDoctorService:
    """Pure business logic for doctor diagnostic checks — no CLI dependencies."""

    def _check_chrome(self) -> CheckResult:
        """Check if Chrome/Chromium is installed and detectable."""
        launcher = ChromeLauncher(session_dir="/tmp", get_used_ports_callback=lambda: set())
        try:
            path = launcher.detect_chrome_path()
            return CheckResult(name="Chrome/Chromium found", status="pass", message=f"Found at {path}")
        except RuntimeError:
            return CheckResult(
                name="Chrome/Chromium found",
                status="fail",
                message="Chrome/Chromium not found",
                fix="Install Google Chrome or set CHROME_PATH environment variable",
            )

    def _check_auth(self) -> CheckResult:
        """Check if any authentication method is configured (API key, config file, or AWS credentials)."""
        if os.environ.get("NOVA_ACT_API_KEY"):
            return CheckResult(
                name="Authentication configured", status="pass", message="API key is configured (env var)"
            )
        try:
            config = read_config()
            if config.api_key:
                return CheckResult(
                    name="Authentication configured", status="pass", message="API key is configured (config file)"
                )
            if getattr(config, "aws_profile", None):
                return CheckResult(
                    name="Authentication configured",
                    status="pass",
                    message=f"AWS profile configured (config file): {config.aws_profile}",
                )
        except (OSError, yaml.YAMLError):
            logger.debug("Failed to read browser config", exc_info=True)
        if has_aws_credentials(None):
            return CheckResult(
                name="Authentication configured",
                status="pass",
                message="AWS credentials are configured",
            )
        return CheckResult(
            name="Authentication configured",
            status="fail",
            message="No authentication configured",
            fix=(
                "export NOVA_ACT_API_KEY=<your-api-key>  OR  act browser setup --api-key <key>"
                "  OR  configure AWS credentials"
            ),
        )

    def _check_session_dir(self) -> CheckResult:
        """Check if session directory is writable."""
        session_dir = get_session_dir()
        try:
            session_dir.mkdir(parents=True, exist_ok=True)
            if os.access(session_dir, os.W_OK):
                return CheckResult(name="Session directory writable", status="pass", message=str(session_dir))
            return CheckResult(
                name="Session directory writable",
                status="fail",
                message=f"Not writable: {session_dir}",
                fix=f"Fix permissions: chmod u+w {session_dir}",
            )
        except OSError as e:
            return CheckResult(
                name="Session directory writable",
                status="fail",
                message=f"Cannot create: {session_dir} ({e})",
                fix=f"Create directory manually: mkdir -p {session_dir}",
            )

    def _check_orphaned_sessions(self) -> CheckResult:
        """Check for orphaned browser sessions."""
        try:
            manager = SessionManager()
            sessions = manager.list_sessions()
            orphaned = [s for s in sessions if s.is_orphaned]
            if orphaned:
                ids = ", ".join(s.session_id for s in orphaned)
                return CheckResult(
                    name="No orphaned sessions",
                    status="fail",
                    message=f"{len(orphaned)} orphaned session(s): {ids}",
                    fix="act browser session prune --ignore-ttl",
                )
            return CheckResult(name="No orphaned sessions", status="pass", message="No orphaned sessions found")
        except (OSError, RuntimeError) as e:
            return CheckResult(name="No orphaned sessions", status="info", message=f"Could not check: {e}")

    def _check_disk_usage(self) -> CheckResult:
        """Check disk usage of CLI data directory."""
        from nova_act.cli.browser.utils.disk_usage import check_disk_usage  # noqa: PLC0415
        from nova_act.cli.core.config import get_browser_cli_dir  # noqa: PLC0415

        cli_dir = get_browser_cli_dir()
        if not cli_dir.exists():
            return CheckResult(name="Disk usage", status="info", message="CLI data directory does not exist yet")
        warning = check_disk_usage(cli_dir)
        if warning:
            return CheckResult(
                name="Disk usage",
                status="fail",
                message=warning,
                fix="act browser session prune --ignore-ttl",
            )
        return CheckResult(name="Disk usage", status="pass", message="CLI data directory within limits")

    def run_checks(self) -> list[CheckResult]:
        """Run all diagnostic checks."""
        return [
            self._check_chrome(),
            self._check_auth(),
            self._check_session_dir(),
            self._check_orphaned_sessions(),
            self._check_disk_usage(),
        ]
