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
"""Centralized browser and CDP configuration constants."""

import signal


class DefaultBrowserConfig:
    """Centralized configuration for browser and CDP settings.

    This class consolidates all magic numbers and configuration constants
    used across session management, Chrome launching, and CDP endpoint management.
    """

    # CDP Configuration
    CDP_PORT_RANGE_START = 9222
    CDP_PORT_RANGE_END = 9322
    CDP_ENDPOINT_TIMEOUT_SECONDS = 15
    CDP_ENDPOINT_POLL_INTERVAL_SECONDS = 0.5
    CDP_VERSION_CHECK_TIMEOUT_SECONDS = 5
    CDP_POLL_REQUEST_TIMEOUT_SECONDS = 1

    # Browser Configuration
    DEFAULT_WINDOW_SIZE = "1600,900"
    CHROME_TERMINATION_GRACE_PERIOD_SECONDS = 2
    CHROME_TERMINATION_SIGNAL = signal.SIGTERM
    CHROME_FORCE_KILL_SIGNAL = signal.SIGKILL
    BROWSER_VERSION_CHECK_TIMEOUT_SECONDS = 5
    BROWSER_PROCESS_NAMES = ("chrome", "chromium", "msedge", "brave")

    # Session Configuration
    SESSION_LOCK_TIMEOUT_SECONDS = 30.0

    # Session Guardrails
    DEFAULT_MAX_ACTIVE_SESSIONS = 5
    SESSION_STALE_TTL_HOURS = 24

    # Act Execution
    DEFAULT_ACT_TIMEOUT_SECONDS = 300
