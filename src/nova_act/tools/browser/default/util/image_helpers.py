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
from typing import Literal, Union

import numpy as np
import requests
from PIL import Image, ImageChops
from playwright.sync_api import Page

from nova_act.tools.browser.default.util.bbox_parser import parse_bbox_string
from nova_act.tools.browser.interface.types.dimensions_dict import DimensionsDict


def get_source_image_from_data_url(screenshot_data_url: str) -> Image.Image:
    """
    Convert a data URL to a PIL Image object.
    """
    # Extract the base64 encoded image data from the data URL
    if "base64," in screenshot_data_url:
        base64_data = screenshot_data_url.split("base64,")[1]
        image_data = base64.b64decode(base64_data)
        return Image.open(io.BytesIO(image_data))
    else:
        # Handle URLs that aren't data URLs
        response = requests.get(screenshot_data_url)
        return Image.open(io.BytesIO(response.content))


def convert_image_to_data_url(image: Image.Image, format_type: str = "jpeg", quality: int | None = 90) -> str:
    """
    Convert a PIL Image to a data URL.
    """
    buffer = io.BytesIO()
    image.save(buffer, format=format_type, quality=quality)
    img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/{format_type.lower()};base64,{img_str}"


def resize_image(screenshot_data_url: str, dimensions: DimensionsDict) -> str:
    """
    Takes a screenshot data URL and resizes it to the specified dimensions.

    Args:
        screenshot_data_url: The data URL of the screenshot, should be base64 encoded.
        dimensions: Dictionary with width and height keys.

    Returns:
        A data URL of the resized image, base64 encoded.
    """
    try:
        # Get the source image from the data URL
        source_image = get_source_image_from_data_url(screenshot_data_url)

        # Resize the image to the specified dimensions
        resized_image = source_image.resize(
            (dimensions["width"], dimensions["height"]),
            Image.Resampling.LANCZOS,
        )

        # Convert the resized image back to a data URL
        return convert_image_to_data_url(resized_image, "jpeg", 90)
    except Exception as e:
        raise RuntimeError(f"Unable to resize image: {str(e)}")


def take_screenshot_as_data_url(
    page: Page,
    full_page: bool = False,
    format_type: Literal["jpeg", "png"] = "jpeg",
    quality: int = 100,
) -> str:
    """
    Takes a screenshot using Playwright and returns it as a data URL.

    Args:
        page: The Playwright Page object.
        full_page: Whether to take a screenshot of the full page or just the viewport.
        format_type: The format of the screenshot (jpeg or png).
        quality: The quality of the screenshot (0-100), only applies to jpeg format.

    Returns:
        A data URL of the screenshot, base64 encoded.
    """
    # Take the screenshot using Playwright
    screenshot_bytes = page.screenshot(
        full_page=full_page,
        type=format_type,
        quality=quality if format_type == "jpeg" else None,
    )

    # Convert the bytes to a base64 string
    base64_str = base64.b64encode(screenshot_bytes).decode("utf-8")

    # Create and return the data URL
    return f"data:image/{format_type};base64,{base64_str}"


def compare_images(image1_data_url: str, image2_data_url: str, threshold: int = 10) -> float:
    """
    Compares two images provided as data URLs and returns the percentage of different pixels.

    Args:
        image1_data_url: The data URL of the first image, base64 encoded.
        image2_data_url: The data URL of the second image, base64 encoded.

    Returns:
        The percentage of pixels that differ between the two images (0.0 to 100.0).

    Raises:
        RuntimeError: If the images cannot be compared due to different sizes or other errors.
    """
    try:
        # Convert data URLs to PIL Images
        image1 = get_source_image_from_data_url(image1_data_url)
        image2 = get_source_image_from_data_url(image2_data_url)

        # Check if images have the same dimensions
        if image1.size != image2.size:
            # Resize the images to match (using the smaller dimensions for both)
            min_width = min(image1.size[0], image2.size[0])
            min_height = min(image1.size[1], image2.size[1])
            image1 = image1.resize((min_width, min_height), Image.Resampling.LANCZOS)
            image2 = image2.resize((min_width, min_height), Image.Resampling.LANCZOS)

        # Convert images to the same mode if they differ
        if image1.mode != image2.mode:
            # Convert to a common mode (RGB is usually a good choice)
            image1 = image1.convert("RGB")
            image2 = image2.convert("RGB")

        # Calculate the difference between the two images
        diff = ImageChops.difference(image1, image2)

        # Convert the difference image to a numpy array
        diff_array = np.array(diff)

        # Calculate the total number of pixels
        total_pixels = image1.width * image1.height

        # For RGB images, consider a pixel different if any channel differs
        if diff_array.ndim == 3:  # RGB or RGBA image
            # Sum across the color channels and check if any channel differs
            diff_pixels = np.sum(np.any(diff_array > threshold, axis=2))
        else:  # Grayscale image
            diff_pixels = np.sum(diff_array > threshold)

        # Calculate the percentage of different pixels
        percentage_diff: float = (diff_pixels / total_pixels) * 100.0

        return percentage_diff

    except Exception as e:
        raise RuntimeError(f"Unable to compare images: {str(e)}")


def crop_image_with_box(image_data: Union[str, Image.Image], box_string: str, increase_size: int = 0) -> Image.Image:
    """
    Crops an image using coordinates specified in a box string.

    Args:
        image_data: Either a data URL string or a PIL Image object
        box_string: A string containing box coordinates in the format "<box>top, left, bottom, right</box>"
        increase_size: Percentage by which to increase the box size (e.g., 10 means 10% larger)

    Returns:
        A cropped PIL Image object

    Raises:
        ValueError: If the box string format is invalid
        RuntimeError: If the image cannot be cropped
    """
    try:
        # Parse the box coordinates
        bbox = parse_bbox_string(box_string)

        # Convert data URL to PIL Image if needed
        if isinstance(image_data, str):
            image = get_source_image_from_data_url(image_data)
        else:
            image = image_data
        top, left, bottom, right = int(bbox.top), int(bbox.left), int(bbox.bottom), int(bbox.right)

        # Calculate the width and height of the box
        box_width = right - left
        box_height = bottom - top

        # Calculate the amount to increase in each direction
        # Purposefully increase height using the box_width and increase width using box_height
        height_increase = int(box_width * (increase_size / 100))
        width_increase = int(box_height * (increase_size / 100))

        # Adjust the box coordinates
        new_left = max(0, left - width_increase)
        new_top = max(0, top - height_increase)
        new_right = min(image.width, right + width_increase)
        new_bottom = min(image.height, bottom + height_increase)

        # Validate that the crop box is within the image dimensions
        width, height = image.size
        if new_left >= width or new_top >= height or new_right > width or new_bottom > height:
            raise ValueError(
                f"Crop box ({new_top}, {new_left}, {new_bottom}, {new_right}) "
                f"exceeds image dimensions ({width}x{height})"
            )

        # Crop the image using the adjusted box coordinates
        cropped_image = image.crop((new_left, new_top, new_right, new_bottom))

        return cropped_image

    except ValueError:
        # Re-raise ValueError for invalid box format or coordinates
        raise
    except Exception as e:
        # Wrap other exceptions in RuntimeError
        raise RuntimeError(f"Unable to crop image: {str(e)}")


def crop_image_with_box_to_data_url(
    image_data: Union[str, Image.Image],
    box_string: str,
    format_type: str = "JPEG",
    quality: int = 100,
) -> str:
    """
    Crops an image using coordinates specified in a box string and returns it as a data URL.

    Args:
        image_data: Either a data URL string or a PIL Image object
        box_string: A string containing box coordinates in the format "<box>top, left, bottom, right</box>"
        format_type: The format of the output image (JPEG, PNG, etc.)
        quality: The quality of the output image (0-100), only applies to JPEG format

    Returns:
        A data URL of the cropped image, base64 encoded

    Raises:
        ValueError: If the box string format is invalid
        RuntimeError: If the image cannot be cropped
    """
    # Crop the image
    cropped_image = crop_image_with_box(image_data, box_string)

    # Convert the cropped image to a data URL
    return convert_image_to_data_url(cropped_image, format_type, quality)
