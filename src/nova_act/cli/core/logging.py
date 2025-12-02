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
"""Centralized logging utilities for Nova Act CLI."""

import logging
import os


def log_api_key_status(logger: logging.Logger) -> str | None:
    """Log Nova Act API key status with appropriate level."""
    api_key = os.getenv("NOVA_ACT_API_KEY")
    if api_key:
        logger.info("NOVA_ACT_API_KEY found in environment")
    else:
        logger.info("NOVA_ACT_API_KEY not found in environment")
    return api_key


def get_live_tail_command(log_group: str) -> str:
    """Get AWS CLI start-live-tail command for a log group."""
    return f"aws logs start-live-tail --log-group-identifiers {log_group}"


def get_follow_command(log_group: str) -> str:
    """Get AWS CLI tail --follow command for a log group."""
    return f"aws logs tail {log_group} --follow"


def get_since_command(log_group: str) -> str:
    """Get AWS CLI tail --since command for a log group."""
    return f"aws logs tail {log_group} --since 1h"
