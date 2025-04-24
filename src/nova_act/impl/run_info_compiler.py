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
import io
import json
import os
import re

from PIL import Image, ImageDraw

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
            margin: 20px;
            background-color: #f5f5f5;
        }}
        h1, h3 {{
            color: #333;
        }}
    </style>
</head>
<body>
    <h1>Action Viewer</h1>
    <h3>Act ID: {act_id}</h3>
    <h3>Prompt: {prompt}</h3>
    {run_info}
</body>
</html>"""


_BBOX_MATCHER = re.compile(r"<box>(\d+),(\d+),(\d+),(\d+)</box>")
_IMAGE_PREFIX_MATCHER = re.compile(r"^data:image/[^;]+;base64,(.+)$")

_LOGGER = setup_logging(__name__)


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


def format_run_info(steps: int, url: str, time: str, image: str, response: str):
    image = _add_bbox_to_image(image, response)

    return f"""
        <div style="border: 1px solid #ddd; border-radius: 8px; padding: 15px;
            margin-bottom: 15px; margin-top:15px; background-color: #f9f9f9;">
            <h4 style="margin:0; color: #333;">Step {steps}</h4>

            <p style="font-size: 14px; display: flex; align-items: center;">
            <strong style="margin-right: 5px;">Current URL:</strong>

            <a href="{url}" target="_blank" style="color: #007bff;
                text-decoration: none; max-width: 800px; overflow: hidden;
                white-space: nowrap; text-overflow: ellipsis; font-size: 14px;">
                {url}
                </a>
            </p>

            <p style="font-size: 14px; color: #666;"><strong>Timestamp:</strong> {time}
            </p>
            <img src="{image}"
                style="max-width: 800px; height: auto; width: 100%;
                border: 1px solid #ccc; padding: 5px;
                margin-bottom: 10px; border-radius: 5px; background-color: #fff;">

            <pre style="background: #f4f4f4; padding: 10px; border-radius: 5px;
                overflow-x: auto; font-size: 14px; white-space: pre-wrap; word-wrap: break-word;
                margin: 0; display: block; border: 1px solid #ddd;">{response}</pre>
        </div>
    """


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

    def compile(self, act: Act) -> str:
        run_info = ""
        for i, step in enumerate(act.steps):
            run_info += format_run_info(
                i + 1,
                step.model_input.active_url,
                str(step.observed_time),
                step.model_input.image,
                step.model_output.awl_raw_program,
            )

        # Compile Workflow View
        html_content = HTML_TEMPLATE.format(
            run_info=run_info,
            act_id=act.id,
            prompt=act.prompt,
        )
        # Add prompt to the name
        prompt_filename_snippet = self._safe_filename(act.prompt, 30)
        file_name_prefix = f"act_{act.id}_{prompt_filename_snippet}"
        output_file_path = os.path.join(self._session_logs_directory, file_name_prefix + ".html")

        try:
            with open(output_file_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            # Compile request and response JSON
            request_response_file_name = f"{file_name_prefix}_calls.json"
            json_file_path = os.path.join(self._session_logs_directory, request_response_file_name)

            step_info = []
            for step in act.steps:
                step_info.append(
                    {"request": step.rawMessage.get("input", {}), "response": step.rawMessage.get("output")}
                )

            with open(json_file_path, "w", encoding="utf-8") as f:
                json.dump(step_info, f)
        except OSError as e:
            _LOGGER.warning(f"Failed to write to file: {e}")

        return output_file_path
