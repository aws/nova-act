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
import os
from datetime import datetime

from playwright.sync_api import Page

from nova_act.impl.actuation.interface.types.dimensions_dict import DimensionsDict
from nova_act.impl.actuation.playwright.util.image_helpers import (
    resize_image,
    take_screenshot_as_data_url,
)


def take_observation(page: Page, dimensions: DimensionsDict | None = None, save_screenshot: bool = False) -> str:
    """
    Takes an observation of the current page state, including a screenshot.

    Args:
        page: The Playwright Page object.
        dimensions: Dictionary with width and height keys for resizing the image.

    Returns:
        A data URL of the resized screenshot.
    """
    # Take a screenshot and get it as a data URL
    screenshot_data_url = take_screenshot_as_data_url(page)
    if dimensions is not None:
        screenshot_data_url = resize_image(screenshot_data_url, dimensions)

    if save_screenshot:
        save_data_url_to_file(screenshot_data_url, f"screenshot_{datetime.now().isoformat()}.jpg")
    return screenshot_data_url


def save_data_url_to_file(data_url: str, file_path: str) -> None:
    """
    Saves a data URL to a file.

    Args:
        data_url: The data URL to save.
        file_path: The path to save the file to.
    """
    # Extract the base64 encoded image data from the data URL
    if "base64," in data_url:
        base64_data = data_url.split("base64,")[1]
        image_data = base64.b64decode(base64_data)

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)

        # Write the image data to a file
        with open(file_path, "wb") as f:
            f.write(image_data)
        print(f"Image saved to {file_path}")
    else:
        raise ValueError("Invalid data URL format")
