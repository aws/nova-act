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
import requests


def verify_certificate(url: str) -> bool:
    """
    Attempts to verify a certificate for a given URL.

    This function simulates the process of verifying a certificate for a URL,
    similar to what a web browser might do. It checks if the certificate is
    valid and can be verified.

    Args:
    url (str): The URL to verify the certificate for.

    Returns:
    bool: True if the certificate is valid and can be verified, False otherwise.

    Raises:
    ValueError: If the input URL is empty or not a string.
    """
    if not isinstance(url, str) or not url:
        raise ValueError("URL must be a non-empty string")
    try:
        response = requests.get(url, verify=True)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        print(f"Certificate for {url} is valid.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Certificate verification failed for {url}: {e}")
        return False
