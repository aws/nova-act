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
from playwright.sync_api import Page

from nova_act.tools.browser.default.util.bbox_parser import bounding_box_to_point
from nova_act.tools.browser.default.util.element_helpers import viewport_dimensions
from nova_act.types.api.step import BboxTLBR


def agent_hover(bbox: BboxTLBR, page: Page) -> None:
    """
    Hover on a point within a bounding box.

    Args:
        bounding_box: A dict representation of a bounding box
        page: Playwright Page object
    """
    bbox.validate_in_viewport(**viewport_dimensions(page))
    point = bounding_box_to_point(bbox)
    page.mouse.move(point["x"], point["y"])
