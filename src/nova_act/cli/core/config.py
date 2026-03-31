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
"""Configuration management for CLI paths and config I/O.

Single source of truth for all CLI directory paths and config file operations.
All CLI paths live under ~/.act_cli — browser CLI under ~/.act_cli/browser,
workflow CLI under ~/.act_cli directly.
"""

from __future__ import annotations

import logging
import os
import stat
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

from nova_act.cli.core.constants import BUILDS_DIR_NAME, CONFIG_DIR_NAME

logger = logging.getLogger(__name__)

# Browser CLI subdirectory under ~/.act_cli
BROWSER_CLI_SUBDIR = "browser"

# Browser CLI config file name
BROWSER_CLI_CONFIG_FILE = "config.yaml"


@dataclass
class BrowserCliConfig:
    """Typed schema for browser CLI configuration (YAML-backed).

    Attributes:
        api_key: Nova Act API key for authentication.
        aws_profile: Default AWS profile name for AWS auth.
        aws_region: Default AWS region for AWS auth.
        workflow_name: Default workflow definition name for AWS auth.
    """

    api_key: str | None = field(default=None)
    aws_profile: str | None = field(default=None)
    aws_region: str | None = field(default=None)
    workflow_name: str | None = field(default=None)


def get_browser_cli_dir() -> Path:
    """Get browser CLI base directory (~/.act_cli/browser)."""
    return get_cli_config_dir() / BROWSER_CLI_SUBDIR


def get_browser_cli_config_file() -> Path:
    """Get browser CLI config file path (~/.act_cli/browser/config.yaml)."""
    return get_browser_cli_dir() / BROWSER_CLI_CONFIG_FILE


def get_log_base_dir() -> Path:
    """Get log base directory (~/.act_cli/browser/session_logs)."""
    return get_browser_cli_dir() / "session_logs"


def read_config() -> BrowserCliConfig:
    """Read browser CLI YAML config file into typed schema.

    Falls back to legacy key=value format for migration support.
    """
    config_file = get_browser_cli_config_file()
    if not config_file.exists():
        # Check legacy location for migration
        return _read_legacy_config()

    try:
        data = yaml.safe_load(config_file.read_text()) or {}
        return BrowserCliConfig(**{k: v for k, v in data.items() if k in BrowserCliConfig.__dataclass_fields__})
    except Exception:
        logger.debug("Failed to parse config %s, returning defaults", config_file, exc_info=True)
        return BrowserCliConfig()


def _read_legacy_config() -> BrowserCliConfig:
    """Read legacy key=value config from ~/.nova-act-cli/config for migration."""
    legacy_file = Path.home() / ".nova-act-cli" / "config"
    if not legacy_file.exists():
        return BrowserCliConfig()

    config: dict[str, str] = {}
    for line in legacy_file.read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            config[key.strip()] = value.strip()

    return BrowserCliConfig(api_key=config.get("api_key"))


def write_config(config: BrowserCliConfig) -> None:
    """Write browser CLI config to YAML file with restrictive permissions."""
    config_dir = get_browser_cli_dir()
    config_file = get_browser_cli_config_file()
    config_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(config_dir, stat.S_IRWXU)  # 0o700

    data = {k: v for k, v in asdict(config).items() if v is not None}
    config_file.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
    os.chmod(config_file, stat.S_IRUSR | stat.S_IWUSR)  # 0o600


def get_cli_config_dir() -> Path:
    """Get workflow CLI configuration directory path (~/.act_cli)."""
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


def get_session_dir() -> Path:
    """Get session directory path for browser session persistence."""
    return get_browser_cli_dir() / "sessions"
