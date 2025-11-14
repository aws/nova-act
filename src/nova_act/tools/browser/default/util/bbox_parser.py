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

from nova_act.types.api.step import BboxTLBR


def parse_bbox_string(bbox_string: str) -> BboxTLBR:
    """Convert a bounding box string to a dictionary representation.

    Args:
        bbox_string: A string in the format "<box>top,left,bottom,right</box>"

    Returns:
        A dictionary with keys 'top', 'bottom', 'left', 'right' representing the bounding rectangle
    """
    bbox_string = bbox_string.strip()
    if not bbox_string.startswith("<box>") or not bbox_string.endswith("</box>"):
        raise ValueError(
            f"Invalid bounding box format. Expected '<box>top,left,bottom,right</box>', got: {bbox_string}"
        )

    # Extract the coordinates
    coords_str = bbox_string.replace("<box>", "").replace("</box>", "").strip()
    if not coords_str:
        raise ValueError(f"Empty coordinates in bounding box: {bbox_string}")

    # Parse coordinates
    try:
        coord_parts = coords_str.split(",")
        if len(coord_parts) != 4:
            raise ValueError(f"Expected 4 coordinates, got {len(coord_parts)}: {bbox_string}")

        coords = [float(coord.strip()) for coord in coord_parts]
    except ValueError as e:
        raise ValueError(f"Invalid coordinate values in bounding box: {bbox_string}. Error: {e}") from e

    return BboxTLBR(*coords)


def bounding_box_to_point(bbox: BboxTLBR) -> Dict[str, float]:
    # Calculate the center point of the bounding box
    center_x = (bbox.left + bbox.right) / 2
    center_y = (bbox.top + bbox.bottom) / 2

    return {"x": center_x, "y": center_y}
