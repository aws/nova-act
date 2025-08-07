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
import sys
import uuid
from typing import Any
from urllib.parse import urlparse

from nova_act.impl.backend import Backend, get_urls_for_backend
from nova_act.types.errors import (
    AuthError,
    InvalidChromeChannel,
    InvalidInputLength,
    InvalidMaxSteps,
    InvalidPath,
    InvalidScreenResolution,
    InvalidTimeout,
    InvalidURL,
    ValidationFailed,
)
from nova_act.util.logging import setup_logging
from nova_act.util.url import verify_certificate

MIN_TIMEOUT_S = 2  # 2 sec
MAX_TIMEOUT_S = 1800  # 30 mins

MAX_PROMPT_LENGTH = 10000
MIN_PROMPT_LENGTH = 1

MIN_SCREEN_SIZE = 600
MAX_SCREEN_SIZE = 10000

MAX_PARAM_LENGTH = 2048

MAX_STEP_LIMIT = 100

_LOGGER = setup_logging(__name__)

SUPPORTED_CHANNELS = {
    "chrome",
    "chromium",
    "msedge",
    "chrome-beta",
    "msedge-beta",
    "chrome-dev",
    "msedge-dev",
    "chrome-canary",
    "msedge-canary",
}


def _get_key_length_by_backend(backend: Backend) -> int:
    return 36


def validate_url(url: str, state: str) -> None:
    """Validate the url value.

    Parameters
    ----------
    url: str
        The url to validate.

    Returns
    -------
    None
    """
    if not isinstance(url, str):
        raise InvalidURL(f"{state} URL provided is not a string.")

    result = urlparse(url)
    if result.scheme != "file" and not all([result.scheme, result.netloc]):
        raise InvalidURL(f"{state} URL provided is invalid. Did you include http:// or https:// ?")


def validate_path(path: str, description: str, empty_directory_allowed: bool = False) -> None:
    """Validate the path value.

    Parameters
    ----------
    path: str
        The path to validate.

    Returns
    -------
    None
    """

    if not isinstance(path, str):
        raise InvalidPath(f"{description} ({path}) path provided is not a string.")

    if not os.path.isdir(path):
        raise InvalidPath(
            f"{description} ({path}) path provided is invalid. Please make sure you point to the right path"
        )
    if not empty_directory_allowed and len(os.listdir(path)) == 0:
        raise InvalidPath(f"{description} ({path}) directory cannot be empty.")


def validate_prompt(prompt: str) -> None:
    """Validate the user prompt.

    Parameters
    ----------
    prompt: str
        The user prompt to validate.

    Returns
    -------
    None
    """
    if not isinstance(prompt, str):
        raise InvalidInputLength("Prompt must be a string.")

    if not (MIN_PROMPT_LENGTH <= len(prompt) <= MAX_PROMPT_LENGTH):
        raise InvalidInputLength(
            f"Prompt length must be between 1 and 10000 characters inclusive. Current length: {len(prompt)}"
        )


def validate_timeout(timeout: int | None) -> None:
    """Validate the timeout value.

    Parameters
    ----------
    timeout: int | None
        The timeout value to validate.

    Returns
    -------
    None
    """
    if timeout is None:
        return
    if not isinstance(timeout, int):
        raise InvalidTimeout("Timeout must be an integer.")
    if timeout < MIN_TIMEOUT_S or timeout > MAX_TIMEOUT_S:
        raise InvalidTimeout(f"Timeout must be between {MIN_TIMEOUT_S} and {MAX_TIMEOUT_S}")


def validate_step_limit(max_steps: int | None) -> None:
    """Validate the max_steps input"""
    if max_steps is None:
        return
    if max_steps >= MAX_STEP_LIMIT:
        raise InvalidMaxSteps(MAX_STEP_LIMIT)


def check_screen_resolution_in_recommended_range(screen_width: int, screen_height: int) -> None:
    # These numbers are +/- 20% of 1920x1080
    in_range = screen_width >= 1536 and screen_width <= 2304 and screen_height >= 864 and screen_height <= 1296
    if not in_range:
        raise InvalidScreenResolution(
            "Screen resolution is not in the recommended range "
            "of +-20% of 1920x1080 ([1536, 2304]x[864, 1296]). Agent performance might be degraded."
        )


def validate_screen_resolution(screen_width: int, screen_height: int) -> None:
    if not (
        screen_width >= MIN_SCREEN_SIZE
        and screen_width <= MAX_SCREEN_SIZE
        and screen_height >= MIN_SCREEN_SIZE
        and screen_height <= MAX_SCREEN_SIZE
    ):
        raise InvalidScreenResolution(
            f"Invalid screen resolution. Acceptable range: [{MIN_SCREEN_SIZE}, {MAX_SCREEN_SIZE}]."
        )
    check_screen_resolution_in_recommended_range(screen_width=screen_width, screen_height=screen_height)


def validate_chrome_channel(chrome_channel: str) -> None:
    if chrome_channel not in SUPPORTED_CHANNELS:
        raise InvalidChromeChannel(
            f"Invalid Chrome channel provided. Supported channels: {', '.join(sorted(SUPPORTED_CHANNELS))}."
        )


def validate_proxy(proxy: dict[str, str] | None) -> None:
    """Validate proxy configuration.

    Parameters
    ----------
    proxy : dict[str, str] | None
        Proxy configuration dictionary with server, username, and password keys.

    Returns
    -------
    None
    """
    if proxy is None:
        return

    if not isinstance(proxy, dict):
        raise ValidationFailed("Proxy must be a dictionary")

    # Check required keys
    if "server" not in proxy:
        raise ValidationFailed("Proxy configuration must contain 'server' key")

    # Validate server format
    server = proxy["server"]
    if not isinstance(server, str):
        raise ValidationFailed("Proxy server must be a string")

    if not (server.startswith("http://") or server.startswith("https://")):
        raise ValidationFailed("Proxy server must start with http:// or https://")

    # Validate optional credentials
    for key in ["username", "password"]:
        if key in proxy and not isinstance(proxy[key], str):
            raise ValidationFailed(f"Proxy {key} must be a string")


def validate_url_ssl_certificate(ignore_https_errors: bool, url: str) -> None:
    """
    Validate the SSL certificate for the given URL.

    Parameters
    ----------
    ignore_https_errors: bool
        Whether to ignore https errors for url to allow website with self-signed certificates
    url: str
        The url to be validated
    """
    if ignore_https_errors is True:
        return

    verify_certificate(url)


def validate_base_parameters(
    extension_path: str,
    starting_page: str,
    backend_uri: str,
    user_data_dir: str | None,
    profile_directory: str | None,
    logs_directory: str | None,
    screen_width: int,
    screen_height: int,
    chrome_channel: str,
    ignore_https_errors: bool,
    use_default_chrome_browser: bool,
    proxy: dict[str, str] | None = None,
) -> None:
    if extension_path:
        validate_path(extension_path, "extension_path")
    validate_url(starting_page, "starting_page")
    validate_url_ssl_certificate(ignore_https_errors, starting_page)
    validate_url(backend_uri, "backend_uri")
    if user_data_dir:
        validate_path(user_data_dir, "user_data_dir", empty_directory_allowed=True)

    if profile_directory:
        validate_path(profile_directory, "profile_directory", empty_directory_allowed=True)

    validate_screen_resolution(screen_width=screen_width, screen_height=screen_height)

    if logs_directory:
        validate_path(logs_directory, "logs_directory", empty_directory_allowed=True)

    validate_chrome_channel(chrome_channel)

    if use_default_chrome_browser:
        if sys.platform != "darwin":
            raise NotImplementedError("use_default_chrome_browser is only supported on macOS")
        if not user_data_dir:
            raise InvalidPath("use_default_chrome_browser requires user_data_dir to be provided")

    validate_proxy(proxy)



def validate_length(
    extension_path: str,
    starting_page: str,
    profile_directory: str | None,
    user_data_dir: str,
    nova_act_api_key: str,
    endpoint_name: str | None,
    cdp_endpoint_url: str | None,
    user_agent: str | None,
    logs_directory: str | None,
    backend: Backend,
) -> None:
    fields = {
        "extension_path": extension_path,
        "starting_page": starting_page,
        "profile_directory": profile_directory,
        "user_data_dir": user_data_dir,
        "endpoint_name": endpoint_name,
        "cdp_endpoint_url": cdp_endpoint_url,
        "user_agent": user_agent,
        "logs_directory": logs_directory,
    }

    for field_name, value in fields.items():
        if value is not None and len(value) >= MAX_PARAM_LENGTH:
            raise InvalidInputLength(f"{field_name} exceeds max length of {MAX_PARAM_LENGTH}")

    if nova_act_api_key is not None and len(nova_act_api_key) != _get_key_length_by_backend(backend):
        raise AuthError(backend_info=get_urls_for_backend(backend), message="Invalid API key length")


