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
"""Authentication utilities for browser CLI commands."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from enum import Enum

from nova_act.cli.core.config import get_browser_cli_config_file, read_config

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when authentication cannot be resolved."""


class AuthMode(str, Enum):
    """Authentication mode for Nova Act CLI."""

    API_KEY = "api-key"
    AWS = "aws"


# Backward-compatible aliases
AUTH_MODE_API_KEY = AuthMode.API_KEY
AUTH_MODE_AWS = AuthMode.AWS

DEFAULT_AWS_REGION = "us-east-1"
DEFAULT_WORKFLOW_NAME = "act-cli"
NOVA_ACT_API_KEY_ENV = "NOVA_ACT_API_KEY"


@dataclass(frozen=True)
class AuthConfig:
    """Resolved authentication configuration.

    Attributes:
        mode: Authentication mode — "api-key" or "aws".
        profile: AWS profile name (only relevant for aws mode).
        region: AWS region (only relevant for aws mode).
        workflow_name: Workflow definition name (only relevant for aws mode).
    """

    mode: AuthMode
    profile: str | None = None
    region: str | None = None
    workflow_name: str | None = None

    @classmethod
    def from_metadata(cls, metadata: dict[str, object]) -> "AuthConfig | None":
        """Reconstruct AuthConfig from persisted session metadata.

        Args:
            metadata: Session metadata dict that may contain an 'auth_config' key.

        Returns:
            AuthConfig if valid auth config found in metadata, None otherwise.
        """
        raw = metadata.get("auth_config")
        if not raw or not isinstance(raw, dict):
            return None
        raw_mode = raw.get("mode")
        if raw_mode not in (AuthMode.API_KEY.value, AuthMode.AWS.value):
            return None
        return cls(
            mode=AuthMode(raw_mode),
            profile=raw.get("profile") if isinstance(raw.get("profile"), str) else None,
            region=raw.get("region") if isinstance(raw.get("region"), str) else None,
            workflow_name=raw.get("workflow_name") if isinstance(raw.get("workflow_name"), str) else None,
        )


def _read_api_key_from_config() -> str | None:
    """Read API key from ~/.act_cli/browser/config.yaml if it exists."""
    try:
        return read_config().api_key
    except Exception:
        logger.debug("Failed to read config file %s", get_browser_cli_config_file(), exc_info=True)
    return None


def has_aws_credentials(profile: str | None) -> bool:
    """Check if AWS credentials are available via boto3.

    Returns False if boto3 is not installed or no credentials are found.
    """
    try:
        import boto3  # noqa: PLC0415
    except ImportError:
        logger.debug("boto3 not installed — AWS auth unavailable")
        return False

    try:
        session = boto3.Session(profile_name=profile)
        return session.get_credentials() is not None
    except Exception:
        logger.debug("Failed to check AWS credentials", exc_info=True)
        return False


def _resolve_api_key_auth() -> AuthConfig:
    """Resolve API key authentication.

    Checks the environment variable first, then falls back to config file.

    Raises:
        AuthenticationError: If no API key is available.
    """
    if os.environ.get(NOVA_ACT_API_KEY_ENV):
        return AuthConfig(mode=AUTH_MODE_API_KEY)
    config_key = _read_api_key_from_config()
    if config_key:
        os.environ[NOVA_ACT_API_KEY_ENV] = config_key
        return AuthConfig(mode=AUTH_MODE_API_KEY)
    raise AuthenticationError(f"Auth mode 'api-key' requires {NOVA_ACT_API_KEY_ENV} environment variable to be set.")


def _resolve_aws_auth(
    profile: str | None,
    region: str | None,
    workflow_name: str | None,
) -> AuthConfig:
    """Resolve AWS authentication.

    Raises:
        AuthenticationError: If NOVA_ACT_API_KEY is set (conflicts with AWS mode).
    """
    if os.environ.get(NOVA_ACT_API_KEY_ENV):
        raise AuthenticationError(
            f"Auth mode 'aws' conflicts with {NOVA_ACT_API_KEY_ENV} environment variable. "
            f"Either unset {NOVA_ACT_API_KEY_ENV} or use --auth-mode api-key."
        )
    return AuthConfig(
        mode=AUTH_MODE_AWS,
        profile=profile,
        region=region or DEFAULT_AWS_REGION,
        workflow_name=workflow_name or DEFAULT_WORKFLOW_NAME,
    )


def _resolve_auto_detect(
    profile: str | None,
    region: str | None,
    workflow_name: str | None,
) -> AuthConfig:
    """Auto-detect authentication from environment.

    Resolution order: env var API key, config file API key, AWS credentials.

    Raises:
        AuthenticationError: If no auth method is available.
    """
    if os.environ.get(NOVA_ACT_API_KEY_ENV):
        logger.debug("Auto-detected auth mode: api-key (NOVA_ACT_API_KEY is set)")
        return AuthConfig(mode=AUTH_MODE_API_KEY)

    config_api_key = _read_api_key_from_config()
    if config_api_key:
        logger.debug("Auto-detected auth mode: api-key (from config file %s)", get_browser_cli_config_file())
        os.environ[NOVA_ACT_API_KEY_ENV] = config_api_key
        return AuthConfig(mode=AUTH_MODE_API_KEY)

    if has_aws_credentials(profile):
        logger.debug("Auto-detected auth mode: aws (AWS credentials found)")
        return AuthConfig(
            mode=AUTH_MODE_AWS,
            profile=profile,
            region=region or DEFAULT_AWS_REGION,
            workflow_name=workflow_name or DEFAULT_WORKFLOW_NAME,
        )

    raise AuthenticationError(
        "No authentication configured. Either:\n"
        f"  - Set {NOVA_ACT_API_KEY_ENV} environment variable for API key auth\n"
        "  - Run 'act browser setup' to store an API key in local config\n"
        "  - Configure AWS credentials (env vars, profile, or IAM role) for AWS auth\n"
        "  - Use --auth-mode to explicitly select an auth method"
    )


def resolve_auth_mode(
    auth_mode: str | None = None,
    profile: str | None = None,
    region: str | None = None,
    workflow_name: str | None = None,
) -> AuthConfig:
    """Resolve authentication mode from explicit flags or auto-detection.

    Resolution order:
    1. If auth_mode is explicitly provided, use it.
    2. If NOVA_ACT_API_KEY env var is set, use api-key mode.
    3. If boto3 can find AWS credentials, use aws mode.
    4. Raise an error if no auth method is available.

    Args:
        auth_mode: Explicit auth mode ("api-key" or "aws"), or None for auto-detect.
        profile: AWS profile name for aws mode.
        region: AWS region for aws mode (defaults to us-east-1).
        workflow_name: Workflow definition name for aws mode (defaults to "act-cli").

    Returns:
        Resolved AuthConfig.

    Raises:
        AuthenticationError: If auth mode cannot be resolved or configuration is invalid.
    """
    import click  # noqa: PLC0415

    try:
        if auth_mode == AUTH_MODE_API_KEY:
            return _resolve_api_key_auth()
        if auth_mode == AUTH_MODE_AWS:
            return _resolve_aws_auth(profile, region, workflow_name)
        return _resolve_auto_detect(profile, region, workflow_name)
    except AuthenticationError as e:
        raise click.ClickException(str(e)) from e
