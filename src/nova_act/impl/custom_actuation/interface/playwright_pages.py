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
from abc import ABC, abstractmethod

from playwright.sync_api import Page


class PlaywrightPageManagerBase(ABC):
    """An object which maintains one or more Playwright Pages."""

    @abstractmethod
    def get_page(self, index: int = -1) -> Page:
        """Get a page by index, or the main page if unspecfied."""

    @property
    @abstractmethod
    def pages(self) -> list[Page]:
        """All of the pages managed by this instance."""
