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
"""CLIDoctor: encapsulates all doctor check logic, result aggregation, and output formatting."""

import json
import logging
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import click

from nova_act.cli.browser.services.session.chrome_launcher import ChromeLauncher
from nova_act.cli.browser.services.session.manager import SessionManager
from nova_act.cli.browser.utils.auth import has_aws_credentials
from nova_act.cli.browser.utils.log_capture import capture_command_log
from nova_act.cli.core.config import get_session_dir, read_config
from nova_act.cli.core.json_output import is_json_mode, json_success
from nova_act.cli.core.output import get_cli_stdout

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CheckResult:
    """Result of a single doctor check."""

    name: str
    status: str
    message: str
    fix: str | None = None


_STATUS_ICONS = {
    "pass": click.style("✓", fg="green"),
    "fail": click.style("✗", fg="red"),
    "info": click.style("ℹ", fg="yellow"),
}


class CLIDoctor:
    """Encapsulates all doctor check logic, result aggregation, and output formatting."""

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
        except Exception:
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

    def _check_playwright(self) -> CheckResult:
        """Check if Playwright Chromium is installed."""
        try:
            from playwright.sync_api import sync_playwright  # noqa: PLC0415

            with sync_playwright() as p:
                executable = p.chromium.executable_path
                if executable and os.path.exists(executable):
                    return CheckResult(
                        name="Playwright Chromium installed",
                        status="pass",
                        message=f"Found at {executable}",
                    )
                return CheckResult(
                    name="Playwright Chromium installed",
                    status="info",
                    message="Playwright installed but Chromium browser not found",
                    fix="Run: python -m playwright install chromium",
                )
        except ImportError:
            return CheckResult(
                name="Playwright Chromium installed",
                status="info",
                message="Playwright not installed (optional)",
                fix="pip install playwright && python -m playwright install chromium",
            )
        except Exception as e:
            return CheckResult(
                name="Playwright Chromium installed",
                status="info",
                message=f"Could not check Playwright: {e}",
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
        except Exception as e:
            return CheckResult(name="No orphaned sessions", status="info", message=f"Could not check: {e}")

    def _check_disk_usage(self) -> CheckResult:
        """Check disk usage of CLI data directory."""
        from nova_act.cli.browser.utils.disk_usage import check_disk_usage
        from nova_act.cli.core.config import get_browser_cli_dir

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
            self._check_playwright(),
            self._check_orphaned_sessions(),
            self._check_disk_usage(),
        ]

    def format_text(self, checks: list[CheckResult], log_path: Path) -> None:
        """Format and output text results to terminal."""
        out = get_cli_stdout()
        passed = sum(1 for c in checks if c.status in ("pass", "info"))
        failed = any(c.status == "fail" for c in checks)
        total = len(checks)

        for check in checks:
            icon = _STATUS_ICONS.get(check.status or "", "?")
            line = f"  {icon} {check.name}: {check.message}"
            click.echo(line, file=out)
            if check.status == "fail" and check.fix:
                click.echo(f"    Fix: {check.fix}", file=out)

        click.echo(f"\n  {passed}/{total} checks passed", file=out)
        click.echo(f"  log_dir: {log_path.parent}", file=out)

        if failed:
            sys.exit(1)

    def format_json(self, checks: list[CheckResult], log_path: Path) -> None:
        """Format and output JSON results."""
        out = get_cli_stdout()
        passed = sum(1 for c in checks if c.status in ("pass", "info"))
        failed = any(c.status == "fail" for c in checks)
        total = len(checks)

        result = {
            "checks": [asdict(c) for c in checks],
            "summary": {"passed": passed, "total": total},
        }
        if failed:
            click.echo(
                json.dumps(
                    {"status": "error", "data": result, "log": str(log_path), "log_dir": str(log_path.parent)},
                    default=str,
                ),
                file=out,
            )
            sys.exit(1)
        json_success(result, log_path=str(log_path), log_dir=str(log_path.parent))

    def run(self, verbose: bool) -> None:
        """Full orchestration: log capture → checks → output."""
        with capture_command_log(
            "doctor",
            session_id=None,
            args={},
            quiet=False,
            verbose=verbose,
        ) as log_path:
            checks = self.run_checks()
            if is_json_mode():
                self.format_json(checks, log_path)
            else:
                self.format_text(checks, log_path)
