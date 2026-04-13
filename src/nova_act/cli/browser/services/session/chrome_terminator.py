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
"""Chrome process termination."""

import logging
import time

import psutil

from nova_act.cli.browser.services.browser_config import DefaultBrowserConfig

logger = logging.getLogger(__name__)


def _is_chrome_process(process: psutil.Process) -> bool:
    """Check if a process is a Chrome browser process."""
    name = process.name().lower()
    return any(browser_name in name for browser_name in DefaultBrowserConfig.BROWSER_PROCESS_NAMES)


class ChromeTerminator:
    """Terminates Chrome browser processes."""

    def terminate(self, pid: int | None) -> None:
        """Terminate Chrome process gracefully, force kill if needed.

        Args:
            pid: Process ID to terminate (None if no process)
        """
        if pid is None:
            return

        try:
            process = psutil.Process(pid)
            if not _is_chrome_process(process):
                return

            process.send_signal(DefaultBrowserConfig.CHROME_TERMINATION_SIGNAL)
            time.sleep(DefaultBrowserConfig.CHROME_TERMINATION_GRACE_PERIOD_SECONDS)

            if process.is_running() and _is_chrome_process(process):
                process.send_signal(DefaultBrowserConfig.CHROME_FORCE_KILL_SIGNAL)
        except (psutil.NoSuchProcess, psutil.AccessDenied, ProcessLookupError, PermissionError) as e:
            logger.debug("Failed to terminate Chrome process %s: %s", pid, e)
