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
import os
from typing import Any, Dict, Optional

from boto3.session import Session
from botocore.exceptions import ClientError

from nova_act import NovaAct
from nova_act.types.hooks import StopHook
from nova_act.util.s3_writer_errors import S3WriterBucketNotFoundError, S3WriterError, S3WriterPermissionError


class S3Writer(StopHook):
    """A convenience utility class for writing NovaAct session files to S3.

    This class implements the StopHook protocol and can be registered with a NovaAct
    instance to automatically upload session files to S3 when the NovaAct instance stops.

    The S3Writer requires the following AWS permissions:
    - s3:ListObjects on the bucket and prefix
    - s3:PutObject on the bucket and prefix

    Error handling:
    - S3WriterBucketNotFoundError: Raised when the specified bucket does not exist
    - S3WriterPermissionError: Raised when there are permission issues with S3 operations
    - S3WriterError: Base class for all S3Writer-related errors

    See the sample script in src/samples/s3_writer_example.py for usage examples.
    """

    def __init__(
        self,
        boto_session: Session,
        s3_bucket_name: str,
        s3_prefix: str = "",
        metadata: Optional[Dict[str, str]] = None,
    ):
        """Initialize the S3Writer.

        Parameters
        ----------
        boto_session : Session
            A boto3 session to use for S3 operations
        s3_bucket_name : str
            The name of the S3 bucket to upload files to
        s3_prefix : str, optional
            A prefix to add to the S3 keys (like a folder path in S3).
            The prefix is used exactly as provided.
        metadata : dict, optional
            A dictionary of metadata key-value pairs to apply to all uploaded S3 objects

        Raises
        ------
        ValueError
            If boto_session is not provided
        S3WriterBucketNotFoundError
            If the specified bucket does not exist
        S3WriterPermissionError
            If the user doesn't have the required permissions
        S3WriterError
            For other S3-related errors
        """
        if boto_session is None:
            raise ValueError("boto_session must be provided")

        self._boto_session = boto_session
        self._s3_bucket_name = s3_bucket_name
        self._s3_prefix = s3_prefix
        self._s3_resource = self._boto_session.resource("s3")
        self._metadata = metadata or {}

        # Check if the bucket exists
        self._check_bucket_exists()

        # Check if the user has ListObjects permission on the bucket/prefix
        self._check_list_objects_permission()

    def _check_bucket_exists(self) -> None:
        """Check if the bucket exists and the user has access to it.

        Raises
        ------
        S3WriterBucketNotFoundError
            If the bucket does not exist
        S3WriterPermissionError
            If the user doesn't have access to the bucket
        S3WriterError
            For other S3-related errors
        """
        try:
            self._s3_resource.meta.client.head_bucket(Bucket=self._s3_bucket_name)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "404":
                raise S3WriterBucketNotFoundError(self._s3_bucket_name, e)
            elif error_code == "403":
                raise S3WriterPermissionError(
                    "HeadBucket",
                    self._s3_bucket_name,
                    e,
                    "You need the 's3:HeadBucket' permission to access this bucket.",
                )
            else:
                raise S3WriterError(f"Error accessing bucket '{self._s3_bucket_name}': {e}", e)

    def _check_list_objects_permission(self) -> None:
        """Check if the user has ListObjects permission on the bucket/prefix.

        Raises
        ------
        S3WriterPermissionError
            If ListObjects permission is not available
        S3WriterError
            For other S3-related errors
        """
        try:
            # Try to list objects with the given prefix to check permissions
            # Limit to 1 to minimize API usage
            # Always use a string for prefix, empty string if no prefix is provided
            prefix = self._s3_prefix if self._s3_prefix else ""
            self._s3_resource.meta.client.list_objects_v2(Bucket=self._s3_bucket_name, Prefix=prefix, MaxKeys=1)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            resource = f"{self._s3_bucket_name}/{self._s3_prefix}"
            if error_code == "AccessDenied":
                additional_info = (
                    "Please ensure you have the 's3:ListObjects' or 's3:ListObjectsV2' "
                    "permission for this bucket and prefix."
                )
                raise S3WriterPermissionError("ListObjects", resource, e, additional_info)
            else:
                raise S3WriterError(
                    f"Error checking ListObjects permission on {resource}: {e}. "
                    f"Please ensure you have the necessary permissions to list and upload objects.",
                    e,
                )

    def set_metadata(self, metadata: Dict[str, str]) -> None:
        """Set or update metadata to be applied to all S3 objects uploaded by this writer.

        Parameters
        ----------
        metadata : dict
            A dictionary of metadata key-value pairs
        """
        if not isinstance(metadata, dict):
            raise TypeError("metadata must be a dictionary")
        self._metadata = metadata

    def _log_upload_start(self, session_id: str) -> None:
        """Log the start of S3 upload."""
        print(f"S3 upload starting for session {session_id}")

    def _log_upload_success(self) -> None:
        """Log successful S3 upload."""
        print(f"S3 upload completed to s3://{self._s3_bucket_name}/{self._s3_prefix}")

    def on_stop(self, nova_act: NovaAct) -> None:
        """Upload session files to S3 when NovaAct is stopping.

        This method is called automatically when the NovaAct instance stops.
        It uploads all files from the session logs directory to S3, applying
        any configured metadata to the S3 objects.

        Parameters
        ----------
        nova_act : NovaAct
            The NovaAct instance that is being stopped
        """
        if nova_act.get_session_id() is None:
            raise ValueError("Session ID is not set. Cannot upload session files to S3.")

        self._log_upload_start(nova_act.get_session_id())

        bucket = self._s3_resource.Bucket(self._s3_bucket_name)

        for root, _, files in os.walk(nova_act.get_logs_directory()):
            for file in files:
                local_path = os.path.join(root, file)
                # Calculate relative path for S3 key
                relative_path = os.path.relpath(local_path, nova_act.get_session_logs_directory())

                # Construct S3 key using the prefix exactly as provided
                s3_key = self._construct_s3_key(nova_act.get_session_id(), relative_path)

                # Upload file
                self._upload_file_to_s3(bucket, local_path, s3_key)

        self._log_upload_success()

    def _construct_s3_key(self, session_id: str, relative_path: str) -> str:
        """Construct an S3 key from the session ID and relative path.

        Parameters
        ----------
        session_id : str
            The NovaAct session ID
        relative_path : str
            The relative path of the file within the logs directory

        Returns
        -------
        str
            The S3 key to use for the file
        """
        # Convert Windows-style backslashes to forward slashes for S3 compatibility
        relative_path = relative_path.replace("\\", "/")

        if self._s3_prefix:
            return f"{self._s3_prefix}{session_id}/{relative_path}"
        else:
            return f"{session_id}/{relative_path}"

    def _upload_file_to_s3(self, bucket: Any, local_path: str, s3_key: str) -> None:
        """Upload a file to S3 with error handling.

        Parameters
        ----------
        bucket
            The S3 bucket resource
        local_path : str
            The local path of the file to upload
        s3_key : str
            The S3 key to use for the file
        """
        try:
            extra_args = self._prepare_extra_s3_args()
            bucket.upload_file(local_path, s3_key, ExtraArgs=extra_args)
            print(f"Uploaded {local_path} to s3://{self._s3_bucket_name}/{s3_key}")
        except ClientError as e:
            self._handle_upload_error(e, local_path, s3_key)

    def _handle_upload_error(self, e: ClientError, local_path: str, s3_key: str) -> None:
        """Handle errors that occur during file upload to S3.

        Parameters
        ----------
        e : ClientError
            The boto3 ClientError that occurred
        local_path : str
            The local path of the file being uploaded
        s3_key : str
            The S3 key being used for the file
        """
        error_code = e.response.get("Error", {}).get("Code", "")
        error_message = e.response.get("Error", {}).get("Message", "")

        if error_code == "AccessDenied":
            error_msg = (
                f"Error uploading {local_path}: Access denied. "
                f"Please ensure you have the 's3:PutObject' permission for "
                f"bucket '{self._s3_bucket_name}' and key '{s3_key}'."
            )
            print(error_msg)
        elif error_code == "NoSuchBucket":
            error_msg = (
                f"Error uploading {local_path}: Bucket '{self._s3_bucket_name}' does not exist. "
                f"Please create the bucket before uploading files."
            )
            print(error_msg)
        else:
            error_msg = f"Error uploading {local_path}: {error_code} - {error_message}. Original error: {e}"
            print(error_msg)

    def _prepare_extra_s3_args(self) -> Optional[Dict[str, Dict[str, str]]]:
        """Prepare extra arguments for S3 upload including metadata.

        Returns
        -------
        dict or None
            A dictionary of extra arguments for S3 upload, or None if no extra args
        """
        if not self._metadata:
            return None

        extra_args = {}
        # Convert all metadata keys and values to strings to comply with S3 requirements
        extra_args["Metadata"] = {str(k): str(v) for k, v in self._metadata.items()}
        return extra_args
