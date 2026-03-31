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
"""Disk usage monitoring for browser CLI data directory."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DISK_WARNING_THRESHOLD_BYTES = 5 * 1024 * 1024 * 1024  # 5GB


def check_disk_usage(base_dir: Path) -> str | None:
    """Return warning message if dir exceeds threshold, else None."""
    try:
        total = sum(f.stat().st_size for f in base_dir.rglob("*") if f.is_file())
        if total >= DISK_WARNING_THRESHOLD_BYTES:
            gb = total / (1024**3)
            return (
                f"Browser CLI data directory is {gb:.1f}GB. Run 'act browser session prune --ignore-ttl' to free space."
            )
    except Exception:
        logger.debug("Failed to check disk usage for %s", base_dir, exc_info=True)
    return None
