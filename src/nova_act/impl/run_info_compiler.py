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
import base64
import html
import io
import json
import os
import re

from PIL import Image, ImageDraw
from typing_extensions import TypedDict, cast

from nova_act.types.act_result import ActResult
from nova_act.types.api.step import StepObjectInput, StepObjectOutput
from nova_act.types.api.trace import ExternalTraceDict
from nova_act.types.errors import ValidationFailed
from nova_act.types.state.act import Act
from nova_act.util.logging import setup_logging

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NovaAct Agent Run</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            max-height: 100vh;
            width: 100vw;
            box-sizing: border-box;
            margin: 0;
            font-size: 14px;
            background: rgb(252, 252, 253);
        }}
        h1, h2, h3, h4 {{
            color: #333;
            margin: 0;
            padding: 8px 0;
        }}
        pre {{
            background: #f4f4f4;
            padding: 10px;
            border-radius: 5px;
            overflow-x: auto;
            font-size: 14px;
            white-space: pre-wrap;
            word-wrap: break-word;
            margin: 0;
            display: block;
        }}
        .action-viewer-title-container {{
            border: 1px solid #ddd;
            padding: 16px 32px 4px;
            background: white;
        }}
        .run-info-container {{
            flex-grow: 1;
            overflow: scroll;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        .run-step-container {{
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 16px;
            margin: 8px 16px;
            background: white;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        .id-container {{
            display: flex;
            font-size: 14px;
            gap: 16px;
            margin-top: 8px;
        }}
        .run-step-body {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 16px;
        }}
        @media (max-width: 767px) {{
            .id-container {{
                display: flex;
                font-size: 14px;
                flex-direction: column;
                gap: 0;
                margin-top: 8px;
            }}
            .run-step-body {{
                grid-template-columns: repeat(1, 1fr);
                display: grid;
                gap: 16px;
            }}
        }}
    </style>
</head>
<body>
    <div class="action-viewer-title-container">
        <h2>Amazon Nova Act Action Viewer</h2>
        <h4>Prompt</h4>
        <pre>{prompt}</pre>
        <div class="id-container">
            <div style="padding: 8px 0;"><b>Session ID:</b> {session_id}</div>
            <div style="padding: 8px 0;"><b>Act ID:</b> {act_id}</div>
        </div>
    </div>
    <div class="run-info-container">
        {run_info}
    </div>
</body>
</html>"""


_BBOX_MATCHER = re.compile(r"<box>(\d+),(\d+),(\d+),(\d+)</box>")
_IMAGE_PREFIX_MATCHER = re.compile(r"^data:image/[^;]+;base64,(.+)$")

_LOGGER = setup_logging(__name__)


class EmptyRequest(TypedDict):
    """An empty request."""


class StepInfo(TypedDict):
    """Information on a /step request/response."""

    request: StepObjectInput | EmptyRequest
    response: StepObjectOutput | None


def _add_bbox_to_image(image: str, response: str) -> str:
    if not image:
        return image

    # Find the first bbox in the response. Right now there can ever only be on bbox. The agent will only take one
    # action at a time and then observe before taking the next one.
    bbox_match = _BBOX_MATCHER.search(response)
    if not bbox_match:
        return image
    top, left, bottom, right = map(int, bbox_match.groups())

    # Strip the data prefix in the base64 image.
    image_match = _IMAGE_PREFIX_MATCHER.match(image)
    if image_match:
        image = image_match.group(1)

    # Add the rectangle to the image.
    pil_image = Image.open(io.BytesIO(base64.b64decode(image)))
    draw = ImageDraw.Draw(pil_image)
    draw.rectangle((left, top, right, bottom), outline="red", width=3)
    image_bytes_io = io.BytesIO()
    pil_image.save(image_bytes_io, format="JPEG")

    # Return the modified image with the data prefix.
    return "data:image/jpeg;base64," + base64.b64encode(image_bytes_io.getvalue()).decode("utf-8")


def format_run_info(
    steps: int, url: str, time: str, image: str, response: str, server_time_s: float | None = None
) -> str:
    image = _add_bbox_to_image(image, response)

    # HTML escape the response to prevent HTML interpretation of <box> tags
    escaped_response = html.escape(response)

    server_time_info = ""
    if server_time_s is not None:
        server_time_info = f"""
            <div>
                <div style="margin-bottom: 4px;font-weight: bold;">Server time:</div>
                <div>{server_time_s:.3f}s</div>
            </div>"""

    return f"""
       <div class="run-step-container">
            <h3 style="margin: 0;color: #333;padding: 0;">Step {steps}</h3>

            <div class="run-step-body">
                <img src="{image}"
                    style="border-radius: 5px;
                    object-fit: contain;
                    background-color: lightblue;
                    width: 100%;">
                <pre style="height: fit-content;">{escaped_response}</pre>
                <div>
                    <div style="margin-bottom: 4px;font-weight: bold;">Timestamp</div>
                    <div>{time}</div>
                </div>
                <div style="text-overflow: ellipsis;white-space: nowrap;overflow: hidden;">
                    <div style="margin-bottom: 4px;font-weight: bold;">Active URL</div>
                    <a href="{url}" target="_blank" style="color: #007bff; text-decoration: none;">
                        {url}
                    </a>
                </div>
                {server_time_info}
            </div>
        </div>
    """


def _write_html_file(session_logs_directory: str, file_name_prefix: str, html_content: str) -> str:
    """
    Write HTML content to a file.

    Args:
        session_logs_directory: Directory to write the file to
        file_name_prefix: Prefix for the file name
        html_content: HTML content to write

    Returns:
        Path to the written file
    """
    output_file_path = os.path.join(session_logs_directory, file_name_prefix + ".html")
    try:
        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        return output_file_path
    except OSError as e:
        _LOGGER.warning(f"Failed to write html to file: {e}")
        return ""


def _extract_step_info(act: Act) -> list[StepInfo]:
    """
    Extract request/response data from act steps.

    Args:
        act: Act object containing steps

    Returns:
        List of request/response data extracted from steps
    """
    step_info = []
    for step in act.steps:
        request: StepObjectInput | EmptyRequest = {}
        if step.model_input:
            request = StepObjectInput(
                screenshot=step.model_input.image,
                prompt=step.model_input.prompt,
                metadata={"activeURL": step.model_input.active_url},
            )
        step_data = StepInfo(
            request=request,
            response=(
                StepObjectOutput(
                    program=step.model_output.program_ast,
                    rawProgramBody=step.model_output.awl_raw_program,
                    requestId=step.model_output.request_id,
                )
                if step.model_output
                else None
            ),
        )
        step_info.append(step_data)
    return step_info


def _write_calls_json_file(session_logs_directory: str, file_name_prefix: str, act: Act) -> None:
    """
    Write request/response calls to a JSON file.

    Args:
        session_logs_directory: Directory to write the file to
        file_name_prefix: Prefix for the file name
        act: Act object containing steps
    """
    try:
        request_response_file_name = f"{file_name_prefix}_calls.json"
        json_file_path = os.path.join(session_logs_directory, request_response_file_name)

        step_info = _extract_step_info(act)

        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(step_info, f, indent=2)
    except OSError as e:
        _LOGGER.warning(f"Failed to write request/response data to file {json_file_path}: {e}")


def _extract_step_traces(act: Act) -> list[ExternalTraceDict]:
    """
    Extract trace data from act steps.

    Args:
        act: Act object containing steps

    Returns:
        List of trace data extracted from steps
    """
    step_traces = []
    for step in act.steps:
        if step.trace is not None:
            step_trace = step.trace.get("external", {})
            step_traces.append(cast(ExternalTraceDict, step_trace))
    return step_traces


def _write_traces_json_file(session_logs_directory: str, file_name_prefix: str, act: Act) -> None:
    """
    Write trace data to a JSON file.

    Args:
        session_logs_directory: Directory to write the file to
        file_name_prefix: Prefix for the file name
        act: Act object containing steps
    """
    try:
        trace_file_name = f"{file_name_prefix}_traces.json"
        json_file_path = os.path.join(session_logs_directory, trace_file_name)
        step_traces = _extract_step_traces(act)

        if step_traces:
            with open(json_file_path, "w", encoding="utf-8") as f:
                json.dump(step_traces, f, indent=2)
    except OSError as e:
        _LOGGER.warning(f"Failed to write trace data to file {json_file_path}: {e}")


class RunInfoCompiler:
    _FILENAME_SUB_RE = re.compile(r'[<>:"/\\|?*\x00-\x1F\s]')

    def __init__(
        self,
        session_logs_directory: str,
    ):
        self._session_logs_directory = session_logs_directory
        if not self._session_logs_directory:
            raise ValidationFailed(f"Invalid logs directory: {self._session_logs_directory}")

    @staticmethod
    def _safe_filename(s: str, max_length: int) -> str:
        # Replace invalid filename characters and whitespace with underscores.
        safe = RunInfoCompiler._FILENAME_SUB_RE.sub("_", s)
        # Strip leading/trailing underscores.
        safe = safe.strip("_")

        return safe[:max_length]

    def _generate_html_content(self, act: Act, result: ActResult | None) -> str:
        """
        Generate HTML content from act steps.

        Args:
            act: Act object containing steps

        Returns:
            Generated HTML content
        """
        run_info = ""
        for i, step in enumerate(act.steps):
            run_info += format_run_info(
                steps=i + 1,
                url=step.model_input.active_url,
                time=str(step.observed_time),
                image=step.model_input.image,
                response=step.model_output.awl_raw_program,
                server_time_s=step.server_time_s,
            )
        if result is not None:
            result_div = f"""
                <div style="background: #f4f4f4;padding: 16px;
                    border-radius: 5px;
                    margin: 0 16px 16px 16px;
                    border: 1px solid #ddd;
                    gap: 8px;display: flex;
                    flex-direction: column;">
                    <div style="font-weight: bold;">Nova Act Result</div>
                    <pre>{result}</pre>
                </div>"""
            run_info += result_div

        # Compile Workflow View
        html_content = HTML_TEMPLATE.format(
            run_info=run_info,
            session_id=act.session_id,
            act_id=act.id,
            prompt=act.prompt,
        )
        return html_content

    def compile(self, act: Act, result: ActResult | None = None) -> str:
        """
        Compile run information from an Act object and write to files.

        Args:
            act: Act object containing steps

        Returns:
            Path to the written HTML file
        """
        # Add prompt to the name
        prompt_filename_snippet = self._safe_filename(act.prompt, 30)
        file_name_prefix = f"act_{act.id}_{prompt_filename_snippet}"

        # Generate HTML content
        html_content = self._generate_html_content(act=act, result=result)

        # Write HTML file
        output_file_path = _write_html_file(
            session_logs_directory=self._session_logs_directory,
            file_name_prefix=file_name_prefix,
            html_content=html_content,
        )

        # Write request/response calls JSON file
        _write_calls_json_file(
            session_logs_directory=self._session_logs_directory, file_name_prefix=file_name_prefix, act=act
        )

        # Write trace JSON file
        _write_traces_json_file(
            session_logs_directory=self._session_logs_directory, file_name_prefix=file_name_prefix, act=act
        )

        return output_file_path
