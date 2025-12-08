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
"""User configuration manager for YAML-based config."""

from typing import Any, Dict

import yaml

from nova_act.cli.core.config import get_cli_config_dir
from nova_act.cli.core.constants import USER_CONFIG_FILE_NAME
from nova_act.cli.core.exceptions import ConfigurationError
from nova_act.cli.core.types import UserConfig


class UserConfigManager:
    """Manages user configuration in YAML format."""

    @staticmethod
    def get_config() -> UserConfig:
        """Load user configuration from YAML file."""
        config_file = get_cli_config_dir() / USER_CONFIG_FILE_NAME
        if not config_file.exists():
            return UserConfigManager._create_default_config()

        try:
            with open(config_file) as f:
                data = yaml.safe_load(f) or {}
            return UserConfigManager._load_user_config(data)
        except Exception as e:
            raise ConfigurationError(f"Failed to load user config: {e}")

    @staticmethod
    def save_config(config: UserConfig) -> None:
        """Save user configuration to YAML file."""
        UserConfigManager._ensure_config_dir()

        try:
            data = UserConfigManager._convert_config_to_dict(config)
            config_file = get_cli_config_dir() / USER_CONFIG_FILE_NAME
            with open(file=config_file, mode="w") as f:
                yaml.dump(data=data, stream=f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            raise ConfigurationError(f"Failed to save user config: {e}")

    @staticmethod
    def _create_default_config() -> UserConfig:
        """Create default user configuration."""
        config = UserConfig()
        UserConfigManager.save_config(config)
        return config

    @staticmethod
    def _ensure_config_dir() -> None:
        """Ensure ~/.act_cli directory exists."""
        get_cli_config_dir().mkdir(exist_ok=True)

    @staticmethod
    def _load_user_config(data: Dict[str, Any]) -> UserConfig:  # type: ignore[explicit-any]
        """Load UserConfig from dictionary."""
        return UserConfig.model_validate(data)

    @staticmethod
    def _convert_config_to_dict(config: UserConfig) -> Dict[str, Any]:  # type: ignore[explicit-any]
        """Convert UserConfig to dictionary."""
        return config.model_dump()
