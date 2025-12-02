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

from nova_act.util.logging import setup_logging

_LOGGER = setup_logging(__name__)


def safe_string(s: str) -> str:
    r"""
    Decode a string containing unicode escape sequences while blocking dangerous ANSI sequences.

    This function:
    1. Decodes unicode escape sequences (like \\u00fc for ü and \\ud83d\\ude05 for 😅)
    2. Removes dangerous ANSI escape sequences (like \\x1b]52)
    3. Handles typescript-style path strings with escaped backslashes (\\\\)
    """
    # First, handle double-escaped unicode sequences (\\uXXXX -> \uXXXX)
    s = s.replace("\\\\u", "\\u")

    # Decode unicode escape sequences using a manual approach
    # This handles both regular unicode and surrogate pairs
    def decode_unicode_escapes(text: str) -> str:
        # Pattern to match \uXXXX sequences
        pattern = r"\\u([0-9a-fA-F]{4})"

        def replace_match(match: re.Match[str]) -> str:
            code_point = int(match.group(1), 16)
            # Check if this is a high surrogate (0xD800-0xDBFF)
            if 0xD800 <= code_point <= 0xDBFF:
                # This is a high surrogate, we need to find the low surrogate
                return chr(code_point)
            # Check if this is a low surrogate (0xDC00-0xDFFF)
            elif 0xDC00 <= code_point <= 0xDFFF:
                return chr(code_point)
            else:
                # Regular unicode character
                return chr(code_point)

        result = re.sub(pattern, replace_match, text)

        # Now handle surrogate pairs by encoding and decoding properly
        try:
            result = result.encode("utf-16", "surrogatepass").decode("utf-16")
        except Exception as e:
            _LOGGER.debug(f"Error decoding surrogate pairs in {result}. {type(e).__name__}: {e}")

        return result

    decoded = decode_unicode_escapes(s)

    # Now remove dangerous ANSI escape sequences
    # Remove ESC sequences (starting with \x1b)
    decoded = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", decoded)  # CSI sequences
    decoded = re.sub(r"\x1b\][^\x07\x1b]*\x07", "", decoded)  # OSC sequences ending with BEL
    decoded = re.sub(r"\x1b\][^\x1b]*\x1b\\", "", decoded)  # OSC sequences ending with ST
    decoded = re.sub(r"\x1b.", "", decoded)  # Other ESC sequences (two chars)

    # Remove BEL character
    decoded = decoded.replace("\x07", "")

    # Handle escaped backslashes (\\) -> (\)
    # This needs to be done carefully to not interfere with other escape sequences
    decoded = decoded.replace("\\\\", "\\")

    return decoded


def decode_awl_raw_program(awl_raw_program: str) -> str:
    """Helper to decode a multi-line AWL program."""
    lines = awl_raw_program.split("\\n")
    decoded_lines = []
    for line in lines:
        decoded_lines.append(safe_string(line))
    awl_program = "\n".join(decoded_lines)
    return awl_program
