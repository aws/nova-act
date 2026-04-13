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
"""Tab operations — create and close browser tabs."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext, Page

    from nova_act import NovaAct


class TabOperationsMixin:
    """Tab management capabilities for BrowserActions."""

    _nova_act: NovaAct

    def create_tab(self, context: BrowserContext, url: str = "about:blank") -> dict[str, object]:
        """Create a new tab, optionally navigating to a URL.

        Returns dict with index, url, title of the new tab.
        """
        new_page = context.new_page()
        if url != "about:blank":
            new_page.goto(url)
        new_page.bring_to_front()
        index = list(context.pages).index(new_page)
        return {"index": index, "url": new_page.url, "title": new_page.title()}

    def close_tab(self, context: BrowserContext, tab_id: int | None, active_page: Page) -> dict[str, object]:
        """Close a tab by index (or the active tab if None).

        Raises:
            ValueError: If this is the last remaining tab.
            IndexError: If tab_id is out of range.

        Returns dict with closed_index, closed_url, closed_title, new_active_index.
        """
        pages = context.pages
        if len(pages) <= 1:
            raise ValueError("Cannot close last tab")

        if tab_id is None:
            target = active_page
            tab_id = list(pages).index(target)
        else:
            if tab_id < 0 or tab_id >= len(pages):
                raise IndexError(f"Index {tab_id} out of range (0-{len(pages) - 1})")
            target = pages[tab_id]

        closed_url = target.url
        closed_title = target.title()
        target.close()

        remaining = context.pages
        new_index = min(tab_id, len(remaining) - 1)
        remaining[new_index].bring_to_front()

        return {
            "closed_index": tab_id,
            "closed_url": closed_url,
            "closed_title": closed_title,
            "new_active_index": new_index,
        }
