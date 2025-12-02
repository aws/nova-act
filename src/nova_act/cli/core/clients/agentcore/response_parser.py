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
"""Response parser utility for handling AWS Bedrock Agent Runtime responses.

This module provides utilities to properly parse StreamingBody responses from
invoke_agent_runtime calls, handling different content types according to AWS specification.
"""

import json
from typing import Dict, Union

from botocore.response import StreamingBody


def parse_invoke_response(response: Dict[str, Union[str, StreamingBody]]) -> Dict[str, str]:
    """Parse invoke_agent_runtime response handling StreamingBody properly.

    Args:
        response: Raw response from boto3 invoke_agent_runtime call

    Returns:
        Dict with parsed response content maintaining backward compatibility
    """
    if not _is_valid_response(response):
        return {"response": str(response)}

    streaming_body = response.get("response")
    if not isinstance(streaming_body, StreamingBody):
        response_value = response.get("response", "")
        return {"response": "" if response_value is None else str(response_value)}

    content_type_raw = response.get("contentType", "")
    content_type = str(content_type_raw) if content_type_raw else ""
    parsed_content = _handle_streaming_body(streaming_body=streaming_body, content_type=content_type)

    return {"response": parsed_content}


def _is_valid_response(response: Union[Dict[str, Union[str, StreamingBody]], str, None]) -> bool:
    """Validate response is a dictionary."""
    return isinstance(response, dict)


def _handle_streaming_body(streaming_body: StreamingBody, content_type: str) -> str:
    """Read content from StreamingBody based on content type.

    Args:
        streaming_body: The StreamingBody object from AWS response
        content_type: MIME type from response headers

    Returns:
        Parsed content as string
    """
    try:
        if "text/event-stream" in content_type:
            return _parse_event_stream(streaming_body)
        elif "application/json" in content_type:
            return _parse_json_response(streaming_body)
        else:
            # Fallback: read as raw text
            return streaming_body.read().decode("utf-8")
    except Exception as e:
        return f"Error parsing response: {str(e)}"


def _parse_event_stream(streaming_body: StreamingBody) -> str:
    """Handle text/event-stream responses.

    Args:
        streaming_body: StreamingBody containing event stream data

    Returns:
        Concatenated event stream content
    """
    content_lines = []

    for line in streaming_body.iter_lines(chunk_size=10):
        if line:
            processed_line = _process_event_line(line)
            if processed_line:
                content_lines.append(processed_line)

    return "\n".join(content_lines)


def _process_event_line(line: bytes) -> str:
    """Process a single event stream line."""
    line_str = line.decode("utf-8")
    if line_str.startswith("data: "):
        data_content = line_str[6:]  # Remove "data: " prefix
        return data_content if data_content.strip() else ""
    return ""


def _parse_json_response(streaming_body: StreamingBody) -> str:
    """Handle application/json responses.

    Args:
        streaming_body: StreamingBody containing JSON data

    Returns:
        JSON content as formatted string
    """
    content_bytes = streaming_body.read()
    content_str = content_bytes.decode("utf-8")

    # Parse and re-format JSON for consistent output
    parsed_json = json.loads(content_str)
    return json.dumps(parsed_json, indent=2)
