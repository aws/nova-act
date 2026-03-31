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
"""Chrome browser launcher and CDP endpoint management.

Handles detecting Chrome installations, launching Chrome with remote debugging
enabled, and connecting to the resulting CDP endpoint. Supports macOS, Linux,
and Windows platforms with automatic CI/Docker environment detection.
"""

import logging
import os
import socket
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from nova_act.cli.browser.services.browser_config import DefaultBrowserConfig
from nova_act.cli.browser.services.session.cdp_endpoint_manager import (
    CdpEndpointManager,
)
from nova_act.cli.browser.services.session.chrome_terminator import ChromeTerminator
from nova_act.cli.core.process import is_process_running

logger = logging.getLogger(__name__)

# Platform -> list of candidate Chrome executable paths
_CHROME_PATHS: dict[str, list[str]] = {
    "darwin": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
    "linux": ["/usr/bin/google-chrome", "/usr/bin/chromium-browser"],
    "win32": [
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ],
}


@dataclass(frozen=True)
class ProfileResolution:
    """Result of resolving a browser profile path to Chrome launch parameters."""

    user_data_dir: Path
    profile_directory: str | None = None


@dataclass(frozen=True)
class LaunchResult:
    """Result of launching Chrome with CDP."""

    process: subprocess.Popen[bytes]
    ws_url: str
    port: int
    user_data_dir: Path


class ChromeLauncher:
    """Launches Chrome with remote debugging and manages the browser process lifecycle.

    Responsible for:
    - Detecting Chrome installations across macOS, Linux, and Windows
    - Finding available CDP ports (avoiding conflicts with other sessions)
    - Launching Chrome with appropriate flags for remote debugging
    - Connecting to the CDP endpoint after launch
    - Resolving and validating user-provided browser profiles
    """

    def __init__(self, session_dir: str, get_used_ports_callback: Callable[[], set[int]]) -> None:
        """Initialize Chrome launcher.

        Args:
            session_dir: Directory for session storage
            get_used_ports_callback: Callback to get ports currently in use
        """
        self.session_dir = session_dir
        self._get_used_ports = get_used_ports_callback
        self.cdp_manager = CdpEndpointManager()
        self._terminator = ChromeTerminator()

    def find_available_port(self, start_port: int | None = None, end_port: int | None = None) -> int:
        """Find available port in range for CDP.

        We manually probe ports rather than letting Chrome auto-select because we
        need to know the port upfront to poll /json/version for the WebSocket URL.
        Chrome's --remote-debugging-port=0 would auto-select, but doesn't reliably
        report the chosen port back to the parent process.

        Note: This is a best-effort check with an inherent TOCTOU race condition —
        the port could be claimed by another process between our check and Chrome's
        bind. The caller handles this via try/except around Chrome launch.

        Args:
            start_port: Start of port range (default: CDP_PORT_RANGE_START)
            end_port: End of port range (default: CDP_PORT_RANGE_END)

        Returns:
            Available port number

        Raises:
            RuntimeError: If no available ports in range
        """
        start_port = start_port or DefaultBrowserConfig.CDP_PORT_RANGE_START
        end_port = end_port or DefaultBrowserConfig.CDP_PORT_RANGE_END

        used_ports = self._get_used_ports()

        for port in range(start_port, end_port + 1):
            if port in used_ports:
                continue

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("localhost", port))
                    return port
                except OSError:
                    continue
        raise RuntimeError(f"No available ports in range {start_port}-{end_port}")

    def detect_chrome_path(self) -> str:
        """Detect Chrome executable for current platform.

        Checks (in order): CHROME_PATH env var, then platform-specific known paths.

        Returns:
            Path to Chrome executable

        Raises:
            RuntimeError: If Chrome not found
        """
        if chrome_path := os.getenv("CHROME_PATH"):
            if os.path.exists(chrome_path):
                return chrome_path

        for path in _CHROME_PATHS.get(sys.platform, []):
            if os.path.exists(path):
                return path

        raise RuntimeError(
            "Chrome/Chromium not found. To fix:\n"
            "  1. Install Google Chrome: https://www.google.com/chrome/\n"
            "  2. Or set CHROME_PATH env var: export CHROME_PATH=/path/to/chrome\n"
            "  3. Or use --executable-path flag: act browser session create --executable-path /path/to/chrome <url>"
        )

    def _validate_browser_executable(self, executable_path: str) -> None:
        """Validate browser executable exists, is executable, and is Chromium-based.

        Args:
            executable_path: Path to browser executable

        Raises:
            RuntimeError: If executable is invalid or not Chromium-based
        """
        if not os.path.exists(executable_path):
            raise RuntimeError(f"Browser executable not found: {executable_path}")
        if not os.access(executable_path, os.X_OK):
            raise RuntimeError(f"Browser executable is not executable: {executable_path}")

        try:
            result = subprocess.run(
                [executable_path, "--version"],
                capture_output=True,
                text=True,
                timeout=DefaultBrowserConfig.BROWSER_VERSION_CHECK_TIMEOUT_SECONDS,
            )
            version_output = result.stdout.lower()
            is_chromium = any(indicator in version_output for indicator in ["chrome", "chromium", "edge"])
            if not is_chromium:
                raise RuntimeError(f"Browser is not Chromium-based: {executable_path}")
        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            raise RuntimeError(f"Failed to verify browser type for {executable_path}: {e}") from e

    def _resolve_user_data_directory(self, session_id: str, profile_path: str | None) -> ProfileResolution:
        """Resolve user data directory from profile path or create new session directory.

        When the profile path points to a Chrome profile subdirectory (e.g. Default/),
        detects this by checking if the parent contains 'Local State' and returns
        the parent as user_data_dir with the subdirectory name as profile_directory.

        Args:
            session_id: Unique identifier for the session
            profile_path: Optional path to existing browser profile directory

        Returns:
            ProfileResolution with user_data_dir and optional profile_directory

        Raises:
            RuntimeError: If profile path is invalid or locked
        """
        if profile_path:
            profile_dir = Path(profile_path).expanduser().resolve()
            if not profile_dir.exists():
                raise RuntimeError(f"Profile directory not found: {profile_path}")
            if not profile_dir.is_dir():
                raise RuntimeError(f"Profile path is not a directory: {profile_path}")

            preferences_file = profile_dir / "Preferences"
            if not preferences_file.exists():
                raise RuntimeError(f"Invalid profile: missing Preferences file in {profile_path}")

            # Best-effort lock check: another Chrome instance could acquire the lock
            # between this check and our launch. The caller handles launch failures
            # via try/except, so this race window is acceptable.
            lock_file = profile_dir / "SingletonLock"
            if lock_file.is_symlink() or lock_file.exists():
                if self._is_lock_stale(lock_file):
                    lock_file.unlink(missing_ok=True)
                else:
                    raise RuntimeError(f"Profile is locked (in use by another browser): {profile_path}")

            # Detect Chrome profile subdirectory: if the parent has 'Local State',
            # this is a profile subdir (e.g. Default/, Profile 1/) inside a Chrome
            # user data directory. Chrome expects --user-data-dir to be the parent.
            parent_local_state = profile_dir.parent / "Local State"
            if parent_local_state.exists():
                return ProfileResolution(
                    user_data_dir=profile_dir.parent,
                    profile_directory=profile_dir.name,
                )

            return ProfileResolution(user_data_dir=profile_dir)
        else:
            user_data_dir = Path(self.session_dir) / session_id / "profile"
            user_data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(user_data_dir, 0o700)
            return ProfileResolution(user_data_dir=user_data_dir)

    def _is_lock_stale(self, lock_file: Path) -> bool:
        """Check if a SingletonLock is stale (owning process no longer running).

        Chrome creates SingletonLock as a symlink to 'hostname-pid'. If the PID
        is no longer running, the lock is stale and safe to remove.

        Returns False (not stale) on error to avoid data corruption from
        two Chrome instances sharing the same profile directory.
        """
        try:
            target = os.readlink(str(lock_file))
            # Format: "hostname-pid"
            pid_str = target.rsplit("-", 1)[-1]
            pid = int(pid_str)
            return not is_process_running(pid)
        except (OSError, ValueError, IndexError):
            # Can't determine lock owner — fail-closed to prevent profile corruption
            # from concurrent Chrome instances. User can manually remove the lock.
            return False

    @staticmethod
    def _detect_ci_environment() -> bool:
        """Detect if running in a CI/Docker environment."""
        ci_env_vars = ("CI", "GITHUB_ACTIONS", "JENKINS_URL", "GITLAB_CI", "CODEBUILD_BUILD_ID", "TF_BUILD")
        if any(os.getenv(var) for var in ci_env_vars):
            return True
        return Path("/.dockerenv").exists()

    def _build_chrome_arguments(
        self, chrome_path: str, port: int, user_data_dir: Path, headless: bool, launch_args: list[str] | None = None
    ) -> list[str]:
        """Build Chrome launch arguments.

        Args:
            chrome_path: Path to Chrome executable
            port: CDP port number
            user_data_dir: User data directory path
            headless: Whether to launch in headless mode
            launch_args: Additional Chrome launch arguments

        Returns:
            List of command-line arguments
        """
        args = [
            chrome_path,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={user_data_dir}",
            f"--window-size={DefaultBrowserConfig.DEFAULT_WINDOW_SIZE}",
            "--no-first-run",
            "--remote-allow-origins=http://localhost",
        ]
        if headless:
            args.append("--headless=new")
        if self._detect_ci_environment():
            args.extend(["--no-sandbox", "--disable-dev-shm-usage"])
        if launch_args:
            args.extend(launch_args)
        return args

    def _launch_and_connect(self, args: list[str], port: int) -> tuple[subprocess.Popen[bytes], str]:
        """Launch Chrome process and connect to CDP endpoint.

        Args:
            args: Chrome launch arguments
            port: CDP port number

        Returns:
            Tuple of (Chrome process, WebSocket URL)

        Raises:
            RuntimeError: If CDP endpoint not available
        """
        process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            ws_url = self.cdp_manager.get_cdp_endpoint(port)
            return process, ws_url
        except BaseException:
            self._terminator.terminate(process.pid)
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
            raise

    def launch_chrome_with_cdp(
        self,
        session_id: str,
        headless: bool,
        executable_path: str | None = None,
        profile_path: str | None = None,
        launch_args: list[str] | None = None,
    ) -> LaunchResult:
        """Launch Chrome with CDP, return LaunchResult with process, ws_url, port, user_data_dir.

        Resolves the Chrome executable, validates it, finds an available port,
        sets up the user data directory, then launches Chrome and waits for the
        CDP endpoint to become available.

        Args:
            session_id: Unique identifier for the session
            headless: Whether to launch in headless mode
            executable_path: Optional path to custom Chromium-based browser executable
            profile_path: Optional path to existing browser profile directory
            launch_args: Additional Chrome launch arguments

        Returns:
            LaunchResult containing Chrome process, WebSocket URL, CDP port, and user data directory

        Raises:
            RuntimeError: If Chrome launch fails or CDP endpoint not available
        """
        chrome_path = executable_path if executable_path else self.detect_chrome_path()
        self._validate_browser_executable(chrome_path)

        port = self.find_available_port()
        resolution = self._resolve_user_data_directory(session_id, profile_path)

        effective_launch_args = list(launch_args) if launch_args else []
        if resolution.profile_directory:
            effective_launch_args.append(f"--profile-directory={resolution.profile_directory}")

        args = self._build_chrome_arguments(
            chrome_path, port, resolution.user_data_dir, headless, effective_launch_args or None
        )

        process, ws_url = self._launch_and_connect(args, port)
        return LaunchResult(process=process, ws_url=ws_url, port=port, user_data_dir=resolution.user_data_dir)
