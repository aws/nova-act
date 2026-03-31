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
"""Shared types for browser CLI commands."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandParams:
    """CLI-facing parameter object grouping the ~16 shared options injected by @browser_command_options.

    This is the raw Click option values — NOT the resolved/SDK-facing BrowserOptions.
    """

    # Session
    session_id: str = "default"
    nova_arg: tuple[str, ...] = ()

    # Browser
    headless: bool = False
    headed: bool = False
    executable_path: str | None = None
    profile_path: str | None = None
    launch_arg: tuple[str, ...] = ()
    ignore_https_errors: bool = True

    # Chrome profile
    use_default_chrome: bool = False
    user_data_dir: str | None = None

    # CDP
    cdp: str | None = None

    # Auth
    auth_mode: str | None = None
    profile: str | None = None
    region: str | None = None
    workflow_name: str | None = None

    # Output
    quiet: bool = False
    verbose: bool = False

    # Screenshot
    no_screenshot_on_failure: bool = False

    # Observe
    observe: bool = False

    # Auto-orientation
    no_snapshot: bool = False
    no_screenshot: bool = False


# Field names that pack_command_params extracts from Click kwargs into CommandParams.
COMMAND_PARAM_FIELDS: frozenset[str] = frozenset(CommandParams.__dataclass_fields__)
