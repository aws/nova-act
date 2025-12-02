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
"""Configuration constants for Nova Act CLI."""

from nova_act.cli.core.theme import ThemeName

# Default configuration values
DEFAULT_REGION = "us-east-1"

# Configuration directory and file names
CONFIG_DIR_NAME = ".act_cli"
USER_CONFIG_FILE_NAME = "config.yml"
STATE_DIR_NAME = "state"
BUILDS_DIR_NAME = "builds"

# Build configuration
BUILD_TEMP_DIR = "/tmp/nova-act-workflow-build/"
BUILD_DIR_PREFIX = "nova-act-build-"
DEFAULT_ENTRY_POINT = "main.py"

# Theme configuration
DEFAULT_THEME = ThemeName.DEFAULT
THEME_ENV_VAR = "ACT_CLI_THEME"
