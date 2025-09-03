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
import os
import subprocess
import tempfile
from pathlib import Path
from platform import freedesktop_os_release, system

from nova_act.types.errors import UnsupportedOperatingSystem, ValidationFailed
from nova_act.util.logging import setup_logging

_LOGGER = setup_logging(__name__)


def should_install_chromium_dependencies() -> bool:
    """Determine whether to install Chromium dependencies.

    OS specifics
    * Amazon Linux below 2023 - glibc version is too low to support the NovaAct Python SDK
    * Amazon Linux 2023 - install Chromium without dependencies

    Returns
    -------
    bool
        True if Chromium dependencies should be installed and False otherwise.

    Raises
    ------
    UnsupportedOperatingSystem
        If the underlying operating system is a version of Amazon Linux below 2023.
    """
    if system() != "Linux":
        return True

    try:
        os_release = freedesktop_os_release()
    except OSError:
        os_release = {}

    if os_release.get("NAME", "") == "Amazon Linux":
        if os_release.get("VERSION", "") == "2023":
            return False
        raise UnsupportedOperatingSystem("NovaAct does not support Amazon Linux below version 2023")

    return True


def rsync_to_temp_dir(src_dir: str, extra_args: list[str] = ['--exclude="Singleton*"']) -> str:
    """rsync from src_dir to a temp_dir after normalizing paths; return the created directory"""
    temp_dir = tempfile.mkdtemp(suffix="_nova_act_user_data_dir")
    normalized_src_dir = src_dir.rstrip("/") + "/"
    if not os.path.exists(normalized_src_dir):
        raise ValueError(f"Source directory {src_dir} does not exist")
    rsync_cmd = ["rsync", "-a", "--delete", *extra_args, normalized_src_dir, temp_dir]
    subprocess.run(rsync_cmd, check=True)
    return temp_dir


def rsync_from_default_user_data(dest_dir: str, extra_args: list[str] = ['--exclude="Singleton*"']) -> str:
    """rsync from system default user_data_dir (MacOs only)"""
    assert system() == "Darwin", "This function is only supported on macOS"

    # empty string at end to create path with trailing slash
    # This ensures rsync copies the contents rather than the folder
    src_dir = os.path.join(str(Path.home()), "Library", "Application Support", "Google", "Chrome", "")

    normalized_dest = os.path.abspath(dest_dir)
    common_path = os.path.commonpath([src_dir, normalized_dest])
    if os.path.samefile(common_path, src_dir):
        raise ValidationFailed(f"Cannot copy Chrome directory into itself or its subdirectory: {dest_dir}")
    os.makedirs(dest_dir, exist_ok=True)
    rsync_cmd = ["rsync", "-a", "--delete", *extra_args, src_dir, dest_dir]
    subprocess.run(rsync_cmd, check=True)
    return dest_dir
