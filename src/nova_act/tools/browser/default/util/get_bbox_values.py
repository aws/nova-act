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
import importlib.resources
from typing import Tuple

from playwright.sync_api import Page

from nova_act.types.api.step import BboxTLWH


def get_bbox_values(page: Page) -> Tuple[dict[int, BboxTLWH], str]:
    """
    Get the bounding box values for all elements on the page and generate a new HTML DOM
    with nova-act-id attributes added to elements that pass the filtering conditions.

    Args:
        page: The Playwright Page object

    Returns:
        A tuple containing:
        - A dictionary mapping element identifiers to their bounding boxes
        - A string containing the modified HTML DOM with nova-act-id attributes
    """

    # Use importlib.resources to load the JavaScript file
    # This works regardless of whether the package is installed from source or as a wheel
    js_code = (
        importlib.resources.files("nova_act.tools.browser.default.util").joinpath("get_simplified_dom.js").read_text()
    )

    # Process all elements in a single JavaScript execution
    # This avoids multiple Python-to-browser round trips
    js_results = page.evaluate(js_code)

    # Extract the bounding box results and modified HTML
    bbox_results = js_results.get("bboxes", {})
    modified_html = js_results.get("modifiedHtml", "")

    # Convert JavaScript object to Python dictionary with proper types
    bbox_dict: dict[int, BboxTLWH] = {}
    for key, value in bbox_results.items():
        bbox_dict[int(key)] = {
            "x": float(value["x"]),
            "y": float(value["y"]),
            "width": float(value["width"]),
            "height": float(value["height"]),
        }

    return bbox_dict, modified_html
