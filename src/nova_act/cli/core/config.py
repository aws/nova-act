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
"""Configuration management for regional workflow support."""

from pathlib import Path

from nova_act.cli.core.constants import BUILDS_DIR_NAME, CONFIG_DIR_NAME


def get_cli_config_dir() -> Path:
    """Get CLI configuration directory path."""
    return Path.home() / CONFIG_DIR_NAME


def get_state_dir() -> Path:
    """Get state directory path."""
    return get_cli_config_dir() / "state"


def get_account_dir(account_id: str) -> Path:
    """Get account directory path."""
    return get_state_dir() / account_id


def get_region_dir(account_id: str, region: str) -> Path:
    """Get region directory path."""
    return get_account_dir(account_id) / region


def get_state_file_path(account_id: str, region: str) -> Path:
    """Get state file path for specific account and region."""
    return get_region_dir(account_id=account_id, region=region) / "workflows.json"


def get_cli_config_file_path() -> Path:
    """Get CLI configuration file path for display purposes."""
    return get_cli_config_dir() / "act_cli_config.json"


def get_builds_dir() -> Path:
    """Get builds directory path."""
    return get_cli_config_dir() / BUILDS_DIR_NAME


def get_workflow_build_dir(workflow_name: str) -> Path:
    """Get build directory path for specific workflow."""
    return get_builds_dir() / workflow_name
