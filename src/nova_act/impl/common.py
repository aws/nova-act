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
import time
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


def rsync_to_temp_dir(src_dir: str) -> str:
    """rsync from src_dir to a temp_dir after normalizing paths; return the created directory"""

    # Note: For security reasons, if refactoring this function in the future, do not take extra
    # args from untrusted callers without sanitizing inputs
    temp_dir = tempfile.mkdtemp(suffix="_nova_act_user_data_dir")
    normalized_src_dir = src_dir.rstrip("/") + "/"
    if not os.path.exists(normalized_src_dir):
        raise ValueError(f"Source directory {src_dir} does not exist")

    if system() == "Windows":
        robo_cmd = ["robocopy", normalized_src_dir, temp_dir, "/MIR", "/XF", '"Singleton*"', "/XD", '"Singleton*"']
        proc = subprocess.run(robo_cmd, capture_output=True, text=True)
        if proc.returncode >= 8:
            raise subprocess.CalledProcessError(proc.returncode, robo_cmd, output=proc.stdout, stderr=proc.stderr)
    else:
        rsync_cmd = ["rsync", "-a", "--delete", '--exclude="Singleton*"', normalized_src_dir, temp_dir]
        subprocess.run(rsync_cmd, check=True)
    return temp_dir


def rsync_from_default_user_data(dest_dir: str) -> str:
    """rsync from system default user_data_dir (MacOs only)"""
    assert system() == "Darwin", "This function is only supported on macOS"

    # Make sure default chrome is not running.
    quit_default_chrome_browser()

    # empty string at end to create path with trailing slash
    # This ensures rsync copies the contents rather than the folder
    src_dir = os.path.join(str(Path.home()), "Library", "Application Support", "Google", "Chrome", "")

    # Note: For security reasons, if refactoring this function in the future, do not take extra
    # args from untrusted callers without sanitizing inputs
    extra_args = ['--exclude="Singleton*"']
    normalized_dest = os.path.abspath(dest_dir)
    common_path = os.path.commonpath([src_dir, normalized_dest])
    if os.path.samefile(common_path, src_dir):
        raise ValidationFailed(f"Cannot copy Chrome directory into itself or its subdirectory: {dest_dir}")
    os.makedirs(dest_dir, exist_ok=True)
    rsync_cmd = ["rsync", "-a", "--delete", *extra_args, src_dir, dest_dir]
    _LOGGER.info(f"rsync from Chrome default user data to {dest_dir}...")
    subprocess.run(rsync_cmd, check=True)
    return dest_dir


def quit_default_chrome_browser() -> None:
    assert system() == "Darwin", "This function is only supported on macOS"

    _LOGGER.info("Quitting Chrome if it's running...")
    subprocess.run(["osascript", "-e", 'quit app "Google Chrome"'], check=True)

    # Wait for it to exit.
    exited = False
    for _ in range(6):  # Wait up to 3 seconds.
        try:
            output = subprocess.check_output(["pgrep", "-x", "Google Chrome"])
            if output.strip():
                time.sleep(0.5)
                continue
        except subprocess.CalledProcessError:
            pass
        exited = True
        break

    assert exited, "Could not quit Chrome"
