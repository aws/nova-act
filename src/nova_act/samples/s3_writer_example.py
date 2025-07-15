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
"""
Example script demonstrating how to use the S3Writer with NovaAct.

This script shows how to:
1. Create a boto3 session with appropriate credentials
2. Create an S3Writer with various configuration options
3. Use the S3Writer with NovaAct to automatically upload session files to S3

Required AWS permissions:
- s3:ListObjects on the bucket and prefix
- s3:PutObject on the bucket and prefix
"""

import boto3
import fire  # type: ignore

from nova_act import NovaAct
from nova_act.util.s3_writer import S3Writer


def main(
    s3_bucket_name: str,
    s3_prefix: str = "s3_writer_example/",
    record_video: bool = False,
) -> None:
    """
    Run a simple NovaAct session and upload the session files to S3.

    Parameters
    ----------
    s3_bucket_name : str
        The name of the S3 bucket to upload files to
    s3_prefix : str, optional
        A prefix to add to the S3 keys (like a folder path in S3)
        The prefix is used exactly as provided
    record_video : bool, optional
        Whether to record video of the browser session
    """
    # Create a boto3 session with appropriate credentials
    boto_session = boto3.Session()

    # Create an S3Writer
    s3_writer = S3Writer(
        boto_session=boto_session,
        s3_bucket_name=s3_bucket_name,
        s3_prefix=s3_prefix,
        metadata={"Example": "S3Writer", "Source": "example_script"},
    )

    # Use the S3Writer with NovaAct
    with NovaAct(
        starting_page="https://www.amazon.com",
        record_video=record_video,
        boto_session=boto_session,
        stop_hooks=[s3_writer],
    ) as nova:
        nova.act("search for a coffee maker")
        nova.act("select the first result")


if __name__ == "__main__":
    fire.Fire(main)
