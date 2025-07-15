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
Custom exception classes for S3Writer component.

This module defines specialized exception classes for the S3Writer component
to provide more specific error handling for different S3-related issues.
"""

from typing import Optional


class S3WriterError(Exception):
    """Base exception class for all S3Writer-related errors."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        """
        Initialize S3WriterError.

        Args:
            message: Descriptive error message
            original_error: Original exception that caused this error, if any
        """
        self.original_error = original_error
        super().__init__(message)


class S3WriterBucketNotFoundError(S3WriterError):
    """Exception raised when the specified S3 bucket does not exist."""

    def __init__(self, bucket_name: str, original_error: Optional[Exception] = None):
        """
        Initialize S3WriterBucketNotFoundError.

        Args:
            bucket_name: Name of the bucket that does not exist
            original_error: Original exception that caused this error, if any
        """
        message = (
            f"S3 bucket '{bucket_name}' does not exist. "
            f"Please verify the bucket name and ensure it exists in your AWS account."
        )
        super().__init__(message, original_error)
        self.bucket_name = bucket_name


class S3WriterPermissionError(S3WriterError):
    """Exception raised when there are permission issues with S3 operations."""

    def __init__(
        self,
        operation: str,
        resource: str,
        original_error: Optional[Exception] = None,
        additional_info: str = "",
    ):
        """
        Initialize S3WriterPermissionError.

        Args:
            operation: The S3 operation that failed (e.g., "ListObjects", "PutObject")
            resource: The S3 resource being accessed (e.g., "bucket/prefix")
            original_error: Original exception that caused this error, if any
            additional_info: Additional information about the error or how to resolve it
        """
        message = f"Insufficient permissions to perform '{operation}' on S3 resource '{resource}'. "

        if additional_info:
            message += f" {additional_info}"

        super().__init__(message, original_error)
        self.operation = operation
        self.resource = resource
