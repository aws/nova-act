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
import json
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from nova_act.util.logging import setup_logging

_LOGGER = setup_logging(__name__)


SET_KEY_TYPE = "autonomy-set-key"
ENCRYPTED_MESSAGE_TYPE = "autonomy-encrypted-message"


class MessageEncrypter:
    """
    Encrypts/decrypts message for extension <-> SDK communication.
    """

    def __init__(self) -> None:
        self._key = secrets.token_hex(256 // 8)  # 256-bit random string
        self._key_bytes = bytes(int(self._key[i : i + 2], 16) for i in range(0, len(self._key), 2))
        self._aesgcm = AESGCM(self._key_bytes)

    def make_set_key_message(self) -> dict:
        """Make a message to set the key"""
        return {"type": SET_KEY_TYPE, "key": self._key}

    def encrypt(self, message: dict) -> dict:
        """Encrypt a message using the key"""
        # Generate a random 96-bit IV (12 bytes)
        iv = os.urandom(12)

        # Encode the message to bytes
        message_bytes = json.dumps(message).encode("utf-8")

        # Encrypt the message
        encrypted = self._aesgcm.encrypt(iv, message_bytes, None)

        # Construct the encrypted message dictionary
        encrypted_message = {
            "encrypted": list(encrypted),
            "iv": list(iv),
            "type": ENCRYPTED_MESSAGE_TYPE,
        }
        return encrypted_message

    def decrypt(self, encrypted_message: dict) -> dict | None:
        """Decrypt a message using the key"""
        if encrypted_message.get("type") != ENCRYPTED_MESSAGE_TYPE:
            raise ValueError("Message is not of type encrypted")

        # Convert IV and encrypted data from lists to bytes
        iv = bytes(encrypted_message["iv"])
        encrypted_bytes = bytes(encrypted_message["encrypted"])
        decrypted_bytes = self._aesgcm.decrypt(iv, encrypted_bytes, None)
        decrypted_json = decrypted_bytes.decode("utf-8")  # Convert bytes to string
        _LOGGER.debug("Decrypted string %s", decrypted_json)
        return json.loads(decrypted_json)  # Convert JSON string back to Python object (dict)
