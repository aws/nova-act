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
import re
import socket
import ssl
from urllib.parse import urlparse, urlunparse

import certifi

from nova_act.types.act_errors import ActStateGuardrailError
from nova_act.types.errors import InvalidCertificate, InvalidURL
from nova_act.types.guardrail import GuardrailCallable, GuardrailDecision, GuardrailInputState
from nova_act.util.path_validator import validate_file_url


def validate_url(
    url: str,
    default_to_https: bool = False,
    allowed_file_open_paths: list[str] = [],
    state_guardrail: GuardrailCallable | None = None,
) -> str:
    """
    Checks for illegal characters, applies allow-list to only permit specific schemes (http, https, etc),
    and verifies that the url is well-formed.

    Parameters
    ----------
    url : str
        The url to validate

    default_to_https : bool
        If True and the given url does not contain a scheme, "https://" is prepended to the returned url

    allowed_file_open_paths : list[str]
        If non-empty, then 'file:' scheme is permitted and the given url must point to a file within the
        list of allowed paths. Else, raise InvalidURL

    state_guardrail : GuardrailCallable
        If defined, will be called to check guardrail policy against the given URL

    Returns
    -------
    str
        The validated url

    Raises
    ------
    InvalidURL
        If the url is invalid or violates security policies
    """

    if not isinstance(url, str):
        raise InvalidURL(f"URL provided is not a string. URL: '{url}'")

    # Check for illegal url characters
    invalid_url_characters = r'[<>"{}|\^`\\ ]'
    if re.search(invalid_url_characters, url):
        raise InvalidURL(f"URL contains invalid characters. URL: '{url}'")

    # Parse into <scheme>://<netloc>/<path>;<params>?<query>#<fragment>
    parsed_url = urlparse(url)

    # If the scheme is missing, either add the default https or raise
    if not parsed_url.scheme:
        if default_to_https:
            url = f"https://{url}"
            parsed_url = urlparse(url)
        else:
            raise InvalidURL(f"Invalid URL, missing 'https://' or 'http://'. URL: '{url}'")

    # To avoid security risks of potentially unsafe URLs (javascript:, etc), only allow a specific set of schemes.
    http_schemes = ["http", "https"]
    allowed_url_schemes = http_schemes + ["about"]

    # 'file' can be unsafe in some situations so only allow the file:// prefix if
    # at least one allowed path is configured.
    if allowed_file_open_paths:
        allowed_url_schemes.append("file")

    if parsed_url.scheme not in allowed_url_schemes:
        message = (
            f"Blocked navigation to a URL with an unsafe scheme: '{parsed_url.scheme}'.\n"
            + f"  Permitted schemes: {allowed_url_schemes}\n"
            + f"  URL: '{url}'\n"
        )
        if parsed_url.scheme == "file":
            message += (
                "  To allow use of 'file://' set "
                + "NovaAct parameter 'security_options=SecurityOptions(allowed_file_open_paths=['/path/to/file'])'"
            )

        raise InvalidURL(message)

    # If the scheme is file, validate that it points to a path that is permitted
    if parsed_url.scheme == "file":
        validate_file_url(url, allowed_file_open_paths)

    # If the scheme is http/https, assert that there is a netloc part of the path
    if parsed_url.scheme in http_schemes and not parsed_url.netloc:
        raise InvalidURL(f"Invalid URL format. URL: '{url}'")

    # If a state guardrail is defined, check it
    if state_guardrail is not None:
        decision = state_guardrail(GuardrailInputState(browser_url=url))
        if decision == GuardrailDecision.BLOCK:
            raise ActStateGuardrailError(f"State guardrail blocked URL: '{url}'")

    return url


def verify_certificate(url: str) -> None:
    """
    Verifies the SSL certificate of a given URL using native ssl library with certifi.

    Args:
    url (str): The URL to verify the certificate for.
    """
    if not isinstance(url, str) or not url:
        raise InvalidURL("URL must be a non-empty string")

    # Parse the URL
    parsed = urlparse(url)

    # Skip certificate verification if scheme is not http or https
    if parsed.scheme and parsed.scheme not in ["http", "https"]:
        return

    # Default unspecified scheme to https and force http->https
    if not parsed.scheme:
        url = f"https://{url}"
        parsed = urlparse(url)
    elif parsed.scheme == "http":
        url = urlunparse(("https",) + parsed[1:])
        parsed = urlparse(url)

    hostname = parsed.hostname
    try:
        context = ssl.create_default_context(cafile=certifi.where())
        with socket.create_connection((hostname, 443), timeout=20) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as secure_socket:
                secure_socket.getpeercert()
                return
    except socket.gaierror:
        raise InvalidCertificate(
            f"SSL Certificate verification failed for {url} as there was an error fetching details for the url"
        )
    except (ssl.SSLCertVerificationError, ssl.SSLError):
        raise InvalidCertificate(f"SSL Certificate verification failed for {url}")
    except ConnectionRefusedError:
        raise InvalidCertificate(f"Connection refused by {url}")
    except Exception:
        raise InvalidCertificate(f"An error occurred while verifying SSL certificate for {url}")
