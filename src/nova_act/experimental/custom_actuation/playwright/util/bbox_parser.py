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
from typing import Dict


def parse_bbox_string(bbox_string: str) -> Dict[str, float]:
    """Convert a bounding box string to a dictionary representation.

    Args:
        bbox_string: A string in the format "<box>top,left,bottom,right</box>"

    Returns:
        A dictionary with keys 'top', 'bottom', 'left', 'right' representing the bounding rectangle
    """
    # Extract the coordinates from the string
    # Remove the <box> and </box> tags and split by commas
    coords_str = bbox_string.replace("<box>", "").replace("</box>", "")
    coords = [float(coord) for coord in coords_str.split(",")]

    # Ensure we have exactly 4 coordinates
    if len(coords) != 4:
        raise ValueError(f"Expected 4 coordinates, got {len(coords)}: {bbox_string}")

    # Extract the coordinates
    top, left, bottom, right = coords

    # Return the bounding rectangle as a dictionary with top, bottom, left, right
    return {"left": left, "top": top, "right": right, "bottom": bottom}


def bounding_box_to_point(box: Dict[str, float]) -> Dict[str, float]:
    # Calculate the center point of the bounding box
    center_x = (box["left"] + box["right"]) / 2
    center_y = (box["top"] + box["bottom"]) / 2

    return {"x": center_x, "y": center_y}
