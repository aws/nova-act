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
import os
import time

import psutil

from nova_act.cli.browser.services.browser_config import DefaultBrowserConfig
from nova_act.cli.core.process import is_process_running

logger = logging.getLogger(__name__)


class ChromeTerminator:
    """Terminates Chrome browser processes."""

    def terminate(self, pid: int | None) -> None:
        """Terminate Chrome process gracefully, force kill if needed.

        Args:
            pid: Process ID to terminate (None if no process)
        """
        if not pid or not is_process_running(pid):
            return

        try:
            process = psutil.Process(pid)
            if not any(name in process.name().lower() for name in DefaultBrowserConfig.BROWSER_PROCESS_NAMES):
                return

            os.kill(pid, DefaultBrowserConfig.CHROME_TERMINATION_SIGNAL)
            time.sleep(DefaultBrowserConfig.CHROME_TERMINATION_GRACE_PERIOD_SECONDS)
            if is_process_running(pid):
                os.kill(pid, DefaultBrowserConfig.CHROME_FORCE_KILL_SIGNAL)
        except (ProcessLookupError, PermissionError, psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.debug("Failed to terminate Chrome process %s: %s", pid, e)
