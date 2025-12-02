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
"""Region utility functions for Nova Act CLI."""

import boto3

DEFAULT_REGION = "us-east-1"


def get_default_region() -> str:
    """Get the default AWS region from boto3 session or fallback to DEFAULT_REGION."""
    session = boto3.Session()
    return session.region_name or DEFAULT_REGION
