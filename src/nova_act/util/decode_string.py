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
import codecs


def decode_string(value: str) -> str:
    """Helper to decode unicode strings"""
    if "\\" in value:
        # Check for unicode escape sequences like \uXXXX
        if "\\u" in value or any(seq in value for seq in ["\\n", "\\t", "\\r", "\\\\", '\\"', "\\'"]):
            try:
                return codecs.decode(value, "unicode_escape")
            except UnicodeDecodeError:
                return value
    return value
