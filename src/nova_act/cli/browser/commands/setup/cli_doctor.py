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
"""CLIDoctor: thin CLI wrapper that delegates checks to CLIDoctorService and handles output formatting."""

import json
import sys
from dataclasses import asdict
from pathlib import Path

import click

from nova_act.cli.browser.services.cli_doctor_service import CheckResult, CLIDoctorService
from nova_act.cli.browser.utils.log_capture import capture_command_log
from nova_act.cli.core.json_output import is_json_mode, json_success
from nova_act.cli.core.output import get_cli_stdout

# Re-export for backward compatibility
__all__ = ["CheckResult", "CLIDoctor"]

_STATUS_ICONS = {
    "pass": click.style("✓", fg="green"),
    "fail": click.style("✗", fg="red"),
    "info": click.style("ℹ", fg="yellow"),
}


class CLIDoctor:
    """Thin CLI wrapper: delegates checks to CLIDoctorService, handles output formatting."""

    def run_checks(self) -> list[CheckResult]:
        """Delegate to CLIDoctorService."""
        return CLIDoctorService().run_checks()

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
