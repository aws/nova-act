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
"""WorkflowRun DTO for passing workflow context data safely."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowRun:
    """Immutable data transfer object for workflow context.

    This DTO safely passes workflow context data between components without
    creating tight coupling or state conflicts.
    """

    workflow_definition_name: str
    workflow_run_id: str
