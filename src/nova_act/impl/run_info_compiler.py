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
import dataclasses
import html
import io
import json
import os
import re
import secrets
from urllib.parse import urlparse

from PIL import Image, ImageDraw
from typing_extensions import TypedDict

from nova_act.types.act_metadata import ActMetadata, _format_duration
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
    <meta http-equiv="Content-Security-Policy"
          content="default-src 'self'; script-src 'nonce-{nonce}';
                   style-src 'self' 'unsafe-inline'; img-src 'self' data:">
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
            padding: 0;
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

        /* Header Section */
        .action-viewer-title-container {{
            border-bottom: 1px solid #ddd;
            padding: 16px 24px;
            background: white;
        }}
        .header-title-row {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 16px;
        }}
        .header-caret {{
            cursor: pointer;
            font-size: 18px;
            color: #666;
            transition: transform 0.2s;
            user-select: none;
            width: 20px;
            text-align: center;
        }}
        .header-caret.collapsed {{
            transform: rotate(-90deg);
        }}
        .header-title {{
            flex: 1;
            font-size: 20px;
            font-weight: bold;
        }}
        .header-controls {{
            margin-top: 16px;
            padding-top: 12px;
            border-top: 1px solid #e0e0e0;
        }}
        .control-btn {{
            background: #f0f0f0;
            border: 1px solid #ddd;
            color: #333;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            transition: background 0.2s;
        }}
        .control-btn:hover {{
            background: #e0e0e0;
        }}
        .header-content {{
            max-height: 1000px;
            overflow: hidden;
            transition: max-height 0.3s ease-out;
        }}
        .header-content.collapsed {{
            max-height: 0;
            transition: max-height 0.2s ease-in;
        }}

        /* Prompt Section */
        .prompt-section {{
            margin-bottom: 16px;
        }}
        .prompt-header {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
            cursor: pointer;
            user-select: none;
        }}
        .prompt-toggle {{
            font-size: 16px;
            color: #666;
            width: 20px;
            text-align: center;
            transition: transform 0.2s;
        }}
        .prompt-toggle.collapsed {{
            transform: rotate(-90deg);
        }}
        .prompt-label {{
            font-weight: bold;
            font-size: 14px;
        }}
        .step-viewer-prompt-container {{
            max-height: 12rem;
            overflow-y: auto;
            background: #f4f4f4;
            padding: 10px;
            border-radius: 5px;
            font-size: 14px;
            white-space: pre-wrap;
            word-wrap: break-word;
            font-family: monospace;
            border: 1px solid #e0e0e0;
        }}
        .prompt-content.collapsed {{
            display: none;
        }}

        /* Metadata Section */
        .metadata-container {{
            display: flex;
            gap: 24px;
            font-size: 14px;
            flex-wrap: wrap;
        }}
        .metadata-item {{
            display: flex;
            gap: 6px;
        }}
        .metadata-item.full-width {{
            flex-basis: 100%;
        }}
        .metadata-label {{
            font-weight: bold;
        }}

        /* Steps Section */
        .run-info-container {{
            flex-grow: 1;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 8px;
            padding: 8px;
        }}
        .run-step-container {{
            border: 1px solid #ddd;
            border-radius: 8px;
            background: white;
        }}
        .step-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 16px;
            cursor: pointer;
            user-select: none;
            background: #f9f9f9;
            border-radius: 8px 8px 0 0;
        }}
        .step-header:hover {{
            background: #f0f0f0;
        }}
        .step-caret {{
            font-size: 16px;
            color: #666;
            transition: transform 0.2s;
            width: 20px;
            text-align: center;
        }}
        .step-caret.collapsed {{
            transform: rotate(-90deg);
        }}
        .step-title {{
            flex: 1;
            font-weight: bold;
            font-size: 16px;
        }}
        .step-body {{
            max-height: 2000px;
            overflow: hidden;
            transition: max-height 0.3s ease-out;
            padding: 16px;
        }}
        .step-body.collapsed {{
            max-height: 0;
            padding: 0 16px;
            transition: max-height 0.2s ease-in;
        }}
        .run-step-body {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 16px;
        }}

        @media (max-width: 767px) {{
            .metadata-container {{
                flex-direction: column;
                gap: 8px;
            }}
            .run-step-body {{
                grid-template-columns: repeat(1, 1fr);
            }}
        }}
    </style>
</head>
<body>
    <div class="action-viewer-title-container">
        <div class="header-title-row">
            <span class="header-caret" id="headerCaret">▼</span>
            <h2 class="header-title">Amazon Nova Act Action Viewer</h2>
        </div>
        <div class="header-content" id="headerContent">
            <div class="prompt-section">
                <div class="prompt-header" id="promptHeader">
                    <span class="prompt-toggle" id="promptToggle">▼</span>
                    <span class="prompt-label">Prompt</span>
                </div>
                <div class="prompt-content" id="promptContent">
                    <div class="step-viewer-prompt-container">{prompt_display}</div>
                </div>
            </div>
            <div class="metadata-container">
                <div class="metadata-item">
                    <span class="metadata-label">Session ID:</span>
                    <span>{session_id}</span>
                </div>
                <div class="metadata-item">
                    <span class="metadata-label">Act ID:</span>
                    <span>{act_id}</span>
                </div>
                <div class="metadata-item full-width">
                    <span class="metadata-label">Steps:</span>
                    <span>{step_count}</span>
                </div>
            </div>
            <div class="header-controls">
                <button class="control-btn" id="toggleAllBtn">Collapse all steps</button>
            </div>
            {time_worked}
        </div>
    </div>
    <div class="run-info-container" id="stepsContainer">
        {run_info}
    </div>
    <script nonce="{nonce}">
        // Header collapse functionality
        const headerContent = document.getElementById('headerContent');
        const headerCaret = document.getElementById('headerCaret');
        let isHeaderCollapsed = false;

        function toggleHeader() {{
            if (!headerContent || !headerCaret) return;
            isHeaderCollapsed = !isHeaderCollapsed;
            if (isHeaderCollapsed) {{
                headerContent.classList.add('collapsed');
                headerCaret.classList.add('collapsed');
            }} else {{
                headerContent.classList.remove('collapsed');
                headerCaret.classList.remove('collapsed');
            }}
        }}

        // Attach header click event
        if (headerCaret) {{
            headerCaret.addEventListener('click', toggleHeader);
        }}

        // Prompt collapse functionality
        const promptContent = document.getElementById('promptContent');
        const promptToggle = document.getElementById('promptToggle');
        const promptHeader = document.getElementById('promptHeader');
        let isPromptCollapsed = false;

        function togglePrompt() {{
            if (!promptContent || !promptToggle) return;
            isPromptCollapsed = !isPromptCollapsed;
            if (isPromptCollapsed) {{
                promptContent.classList.add('collapsed');
                promptToggle.classList.add('collapsed');
            }} else {{
                promptContent.classList.remove('collapsed');
                promptToggle.classList.remove('collapsed');
            }}
        }}

        // Attach prompt click event
        if (promptHeader) {{
            promptHeader.addEventListener('click', togglePrompt);
        }}

        // Update toggle all button text based on actual step states
        function updateToggleAllButton() {{
            const toggleAllBtn = document.getElementById('toggleAllBtn');
            const allSteps = document.querySelectorAll('.step-body');

            if (!toggleAllBtn || allSteps.length === 0) return;

            // Check if any steps are collapsed
            const anyCollapsed = Array.from(allSteps).some(step => step.classList.contains('collapsed'));

            if (anyCollapsed) {{
                toggleAllBtn.textContent = 'Expand all steps';
            }} else {{
                toggleAllBtn.textContent = 'Collapse all steps';
            }}
        }}

        // Step collapse functionality
        function toggleStep(headerElement) {{
            const stepContainer = headerElement.parentElement;
            const stepBody = stepContainer.querySelector('.step-body');
            const caret = headerElement.querySelector('.step-caret');

            if (stepBody.classList.contains('collapsed')) {{
                stepBody.classList.remove('collapsed');
                caret.classList.remove('collapsed');
            }} else {{
                stepBody.classList.add('collapsed');
                caret.classList.add('collapsed');
            }}

            // Update button text after manual toggle
            updateToggleAllButton();
        }}

        // Attach step click events
        document.addEventListener('DOMContentLoaded', function() {{
            const stepHeaders = document.querySelectorAll('.step-header');
            stepHeaders.forEach(header => {{
                header.addEventListener('click', function() {{
                    toggleStep(this);
                }});
            }});
        }});

        // Toggle all steps with single button
        function toggleAllSteps() {{
            const allSteps = document.querySelectorAll('.step-body');
            const allCarets = document.querySelectorAll('.step-caret');
            const toggleAllBtn = document.getElementById('toggleAllBtn');

            // Check current state
            const anyCollapsed = Array.from(allSteps).some(step => step.classList.contains('collapsed'));

            if (anyCollapsed) {{
                // Expand all
                allSteps.forEach(step => step.classList.remove('collapsed'));
                allCarets.forEach(caret => caret.classList.remove('collapsed'));
                toggleAllBtn.textContent = 'Collapse all steps';
            }} else {{
                // Collapse all
                allSteps.forEach(step => step.classList.add('collapsed'));
                allCarets.forEach(caret => caret.classList.add('collapsed'));
                toggleAllBtn.textContent = 'Expand all steps';
            }}
        }}

        // Attach toggle all button click event
        const toggleAllBtn = document.getElementById('toggleAllBtn');
        if (toggleAllBtn) {{
            toggleAllBtn.addEventListener('click', toggleAllSteps);
        }}

        // Initialize button text on page load
        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', function() {{
                try {{
                    updateToggleAllButton();
                }} catch (e) {{
                    // Silently fail
                }}
            }});
        }} else {{
            try {{
                updateToggleAllButton();
            }} catch (e) {{
                // Silently fail
            }}
        }}
    </script>
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
    screenshotWithBbox: str | None


@dataclasses.dataclass
class StepExtractionOutput:
    """Output structure for step extraction."""

    steps: list[StepInfo]
    metadata: ActMetadata


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


def sanitize_url(url: str) -> str:
    """
    Escapes any HTML which might be in the given string, and removes any dangerous URI schemes
    """
    safe_url_schemes = ["http", "https", "about"]

    url = html.escape(url)
    result = urlparse(url)
    if result.scheme and result.scheme not in safe_url_schemes:
        url = f"redacted_url_with_potentially_unsafe_schema='{result.scheme}'"
    return url


def format_run_info(
    steps: int, url: str, time: str, image: str, response: str, server_time_s: float | None = None
) -> str:
    image = _add_bbox_to_image(image, response)

    # HTML escape the url and response to prevent HTML interpretation of <box> tags and to protect against xss
    escaped_response = html.escape(response)
    escaped_image = html.escape(image)
    escaped_time = html.escape(time)
    escaped_url = sanitize_url(url)

    server_time_info = ""
    if server_time_s is not None:
        server_time_info = f"""
            <div>
                <div style="margin-bottom: 4px;font-weight: bold;">Server time:</div>
                <div>{server_time_s:.3f}s</div>
                <div style="font-size: 0.85em; color: #666; margin-top: 4px;">
                    (Server processing time for this step. Total act time includes
                    client-side processing, network latency, and browser actions.)
                </div>
            </div>"""

    return f"""
       <div class="run-step-container">
            <div class="step-header">
                <span class="step-caret">▼</span>
                <span class="step-title">Step {steps}</span>
            </div>
            <div class="step-body">
                <div class="run-step-body">
                    <img src="{escaped_image}"
                        style="border-radius: 5px;
                        object-fit: contain;
                        background-color: lightblue;
                        width: 100%;">
                    <pre style="height: fit-content;">{escaped_response}</pre>
                    <div>
                        <div style="margin-bottom: 4px;font-weight: bold;">Timestamp</div>
                        <div>{escaped_time}</div>
                    </div>
                    <div style="text-overflow: ellipsis;white-space: nowrap;overflow: hidden;">
                        <div style="margin-bottom: 4px;font-weight: bold;">Active URL</div>
                        <a href="{escaped_url}" target="_blank" style="color: #007bff; text-decoration: none;">
                            {escaped_url}
                        </a>
                    </div>
                    {server_time_info}
                </div>
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


def _extract_step_info(act: Act, result: ActResult | None = None) -> StepExtractionOutput:
    """
    Extract request/response data from act steps with time worked.

    Args:
        act: Act object containing steps
        result: ActResult object containing metadata (optional)

    Returns:
        Dictionary with steps list and metadata including time worked
    """
    step_info_list = []
    for step in act.steps:
        request: StepObjectInput | EmptyRequest = {}
        screenshot_with_bbox = None
        if step.model_input:
            request = StepObjectInput(
                screenshot=step.model_input.image,
                prompt=step.model_input.prompt,
                metadata={"activeURL": step.model_input.active_url},
            )
            screenshot_with_bbox = _add_bbox_to_image(
                step.model_input.image, step.model_output.awl_raw_program if step.model_output else ""
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
            screenshotWithBbox=screenshot_with_bbox,
        )
        step_info_list.append(step_data)

    # Create wrapper with metadata using ActMetadata
    metadata = ActMetadata(
        session_id=act.session_id,
        act_id=act.id,
        num_steps_executed=len(act.steps),
        start_time=act.start_time,
        end_time=act.end_time,
        prompt=act.prompt,
        step_server_times_s=[],
        time_worked_s=result.metadata.time_worked_s if result else None,
        human_wait_time_s=result.metadata.human_wait_time_s if result else 0.0,
    )

    output = StepExtractionOutput(
        steps=step_info_list,
        metadata=metadata,
    )

    return output


def _write_calls_json_file(
    session_logs_directory: str, file_name_prefix: str, act: Act, result: ActResult | None = None
) -> None:
    """
    Write request/response calls to a JSON file.

    Args:
        session_logs_directory: Directory to write the file to
        file_name_prefix: Prefix for the file name
        act: Act object containing steps
        result: ActResult object containing metadata (optional)
    """
    try:
        request_response_file_name = f"{file_name_prefix}_calls.json"
        json_file_path = os.path.join(session_logs_directory, request_response_file_name)

        step_info = _extract_step_info(act, result)

        output_dict = dataclasses.asdict(step_info)
        # Convert to dict and filter out None time_worked_s and zero human_wait_time_s
        if output_dict["metadata"]["time_worked_s"] is None:
            del output_dict["metadata"]["time_worked_s"]
            del output_dict["metadata"]["human_wait_time_s"]

        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(output_dict, f, indent=2)
    except OSError as e:
        _LOGGER.warning(f"Failed to write request/response data to file {json_file_path}: {e}")


def _extract_step_traces(act: Act) -> list[ExternalTraceDict | None]:
    """
    Extract trace data from act steps.

    Args:
        act: Act object containing steps

    Returns:
        List of trace data extracted from steps
    """
    step_traces: list[ExternalTraceDict | None] = []
    for step in act.steps:
        if step.trace is not None:
            step_trace = step.trace.get("external")
            step_traces.append(step_trace)
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
            result: ActResult object containing metadata (optional)

        Returns:
            Generated HTML content
        """

        # Extract time worked from result metadata
        time_worked_display = ""
        if result and result.metadata.time_worked_s is not None:
            time_worked_str = _format_duration(result.metadata.time_worked_s)
            if result.metadata.human_wait_time_s > 0:
                human_wait_str = _format_duration(result.metadata.human_wait_time_s)
                time_worked_display = (
                    f'<div style="padding: 8px 0;"><b>Time Worked:</b> {time_worked_str} '
                    f'<span style="color: #666;">(excluding {human_wait_str} human wait)</span></div>'
                )
            else:
                time_worked_display = f'<div style="padding: 8px 0;"><b>Time Worked:</b> {time_worked_str}</div>'

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
            # Escape any HTML which might be in serialized ActResult string to avoid risk
            # of xss vulnerabilities in model response
            escaped_result_str = html.escape(str(result))
            result_div = f"""
                <div style="background: #f4f4f4;padding: 16px;
                    border-radius: 5px;
                    margin: 0 16px 16px 16px;
                    border: 1px solid #ddd;
                    gap: 8px;display: flex;
                    flex-direction: column;">
                    <div style="font-weight: bold;">Nova Act Result</div>
                    <pre>{escaped_result_str}</pre>
                </div>"""
            run_info += result_div

        # Prepare prompt for display (no truncation, using scrollable container)
        prompt_display = html.escape(act.prompt)

        # Calculate step count
        step_count = len(act.steps)

        # Generate a cryptographically secure nonce for CSP
        nonce = secrets.token_urlsafe(32)

        # Compile Workflow View
        html_content = HTML_TEMPLATE.format(
            run_info=run_info,
            session_id=act.session_id,
            act_id=act.id,
            prompt_display=prompt_display,
            step_count=step_count,
            nonce=nonce,
            time_worked=time_worked_display,
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
            session_logs_directory=self._session_logs_directory,
            file_name_prefix=file_name_prefix,
            act=act,
            result=result,
        )

        # Write trace JSON file
        _write_traces_json_file(
            session_logs_directory=self._session_logs_directory, file_name_prefix=file_name_prefix, act=act
        )

        return output_file_path

    def write_session_summary(
        self,
        session_id: str,
        total_time_worked_s: float,
        total_human_wait_s: float,
        act_count: int,
    ) -> None:
        """
        Write session-level summary to JSON file.

        Args:
            session_id: Session identifier
            total_time_worked_s: Total time worked across all acts in seconds
            total_human_wait_s: Total human wait time across all acts in seconds
            act_count: Number of act calls in the session
        """
        try:
            summary_file_name = "session_summary.json"
            json_file_path = os.path.join(self._session_logs_directory, summary_file_name)

            summary_data = {
                "session_id": session_id,
                "total_time_worked_s": total_time_worked_s,
                "total_human_wait_time_s": total_human_wait_s,
                "act_count": act_count,
            }

            with open(json_file_path, "w", encoding="utf-8") as f:
                json.dump(summary_data, f, indent=2)
        except OSError as e:
            _LOGGER.warning(f"Failed to write session summary to file {json_file_path}: {e}")
