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
"""Extraction and inspection commands.

This package groups extraction-related commands:
- get_content: retrieve page content
- extract: AI-powered data extraction
- screenshot: capture page screenshots
- query: DOM element queries
- style: CSS style inspection
- evaluate: JavaScript evaluation
- diff: page content diffing

Note: Commands are NOT re-exported here to avoid shadowing submodule names,
which breaks unittest.mock.patch() on Python 3.10. Import commands directly
from their submodules (e.g., from nova_act.cli.browser.commands.extraction.extract import extract).
"""
