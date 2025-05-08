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
import socket
import ssl
from urllib.parse import urlparse, urlunparse

import certifi

from nova_act.types.errors import InvalidCertificate
from nova_act.util.logging import setup_logging

_LOGGER = setup_logging(__name__)


def verify_certificate(url: str) -> None:
    """
    Verifies the SSL certificate of a given URL using native ssl library with certifi.

    Args:
    url (str): The URL to verify the certificate for.
    """
    if not isinstance(url, str) or not url:
        raise ValueError("URL must be a non-empty string")

    # Parse the URL
    parsed = urlparse(url)

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
