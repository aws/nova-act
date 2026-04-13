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
"""AgentCore browser profile session provider.

Persists browser state server-side via AgentCore browser profiles.
State is saved and restored by the AgentCore service directly -
no StorageState dicts are transferred through the client.
"""

from __future__ import annotations

import json
import logging
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Protocol, cast

from playwright._impl._api_structures import SetCookieParam
from playwright.sync_api import StorageState

from nova_act.browser_auth.browser_session_provider import BrowserSessionProvider
from nova_act.types.errors import BrowserAuthError


class _ControlPlaneClient(Protocol):
    """Typing protocol for the AgentCore control plane boto3 client."""

    def create_browser_profile(self, **kwargs: object) -> dict[str, object]: ...
    def get_browser_profile(self, **kwargs: object) -> dict[str, object]: ...
    def list_browser_profiles(self, **kwargs: object) -> dict[str, object]: ...


class _DataPlaneClient(Protocol):
    """Typing protocol for the AgentCore data plane boto3 client."""

    def save_browser_session_profile(self, **kwargs: object) -> dict[str, object]: ...


_LOGGER = logging.getLogger(__name__)

# Local cache for AgentCore profile IDs. The AgentCore API only supports
# GetBrowserProfile by profile ID (not by name), so we cache the mapping
# from profile name to profile ID locally to avoid a ListBrowserProfiles
# call on every session start. Cache files are written with 0o600
# permissions (owner read/write only) via atomic tmp+rename.
_CACHE_DIR = Path.home() / ".nova-act" / "agentcore-profiles"

# Browser profile statuses that indicate the profile is usable.
# Full status enum: READY | SAVING | DELETING | DELETED
# https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-agentcore-control/client/get_browser_profile.html
_USABLE_PROFILE_STATUSES = {"READY", "SAVING"}


class AgentCoreBrowserSessionProvider(BrowserSessionProvider):
    """Browser session provider backed by AgentCore server-side profiles.

    AgentCore browser profiles persist browser state (cookies
    and localStorage) server-side. When a session starts
    with a ``profileConfiguration``, state is restored automatically
    by the AgentCore service. When ``save_session()`` is called,
    the service captures the current browser state without
    transferring it through the client.

    Profile IDs are auto-created on first use and cached locally
    at ``~/.nova-act/agentcore-profiles/{name}.json``.

    Example::

        from nova_act import NovaAct
        from nova_act.browser_auth import AgentCoreBrowserSessionProvider

        provider = AgentCoreBrowserSessionProvider(
            profile="outlook_agent",
            region="us-east-1",
        )
        with provider.cdp_session() as (ws_url, headers):
            with NovaAct(
                cdp_endpoint_url=ws_url,
                cdp_headers=headers,
                browser_auth=provider,
                starting_page="https://outlook.office365.com",
            ) as nova:
                nova.act("Check my inbox")
        # Profile saved automatically by the SDK on exit

    Args:
        profile: Profile name passed to AgentCore's
            ``create_browser_profile``. Defaults to ``"default"``.
        region: AWS region for AgentCore API calls.
            Defaults to ``"us-east-1"``.
        cache_dir: Directory for caching the profile name to ID
            mapping locally. The AgentCore API only supports lookup
            by profile ID, so this avoids a ListBrowserProfiles call
            on every session start. Files are written with 0o600
            permissions (owner read/write only).
            Defaults to ``~/.nova-act/agentcore-profiles``.
    """

    def __init__(
        self,
        profile: str = "default",
        *,
        region: str = "us-east-1",
        cache_dir: str | Path = _CACHE_DIR,
    ) -> None:
        self._profile = profile
        self._region = region
        self._cache_dir = Path(cache_dir).expanduser()
        self._cache_path = self._cache_dir / f"{profile}.json"

        # Resolved lazily on first use
        self._profile_id: str | None = None

        # Bound after cdp_session() starts
        self._browser_identifier: str | None = None
        self._session_id: str | None = None

    @property
    def name(self) -> str:
        return "AgentCoreBrowserSessionProvider"

    @property
    def profile_name(self) -> str:
        """The profile name as passed to the constructor."""
        return self._profile

    @property
    def profile_id(self) -> str:
        """The AgentCore profile ID.

        Resolved lazily on first access: checks local cache,
        validates via GetBrowserProfile, searches by name via
        ListBrowserProfiles, or creates a new profile.
        """
        if self._profile_id is None:
            self._profile_id = self._resolve_or_create_profile()
        return self._profile_id

    @property
    def profile_configuration(self) -> dict[str, str]:
        """Profile configuration for ``cdp_session()``.

        Returns a dict compatible with ``ProfileConfiguration``
        and the ``start_browser_session`` API.
        """
        return {"profileIdentifier": self.profile_id}

    def bind_session(self, browser_identifier: str, session_id: str) -> None:
        """Bind browser and session IDs for save operations.

        Must be called after ``cdp_session()`` starts to
        provide the IDs needed by ``save_browser_session_profile``.

        Args:
            browser_identifier: The browser identifier from the
                session start response.
            session_id: The session ID from the session start
                response.
        """
        self._browser_identifier = browser_identifier
        self._session_id = session_id
        _LOGGER.debug(
            "Bound session: browser=%s, session=%s",
            browser_identifier,
            session_id,
        )

    @contextmanager
    def cdp_session(self) -> Generator[tuple[str, dict[str, str]], None, None]:
        """Manage an AgentCore browser session with profile persistence.

        Creates a ``browser_session`` with the profile configuration
        attached, binds session IDs automatically, and yields the
        WebSocket URL and headers for NovaAct CDP connection.

        Profile save happens via the SDK's ``save_session()`` hook
        when ``NovaAct`` exits, before this context manager exits.

        Yields:
            A tuple of ``(ws_url, headers)`` for CDP connection.

        Raises:
            BrowserAuthError: If the session cannot be started or
                the profile cannot be resolved.
        """
        try:
            from bedrock_agentcore.tools.browser_client import browser_session
            from bedrock_agentcore.tools.config import ProfileConfiguration
        except ImportError as exc:
            raise BrowserAuthError(
                "bedrock-agentcore package is required for "
                "AgentCoreBrowserSessionProvider. "
                "Install it with: pip install bedrock-agentcore"
            ) from exc

        profile_config = ProfileConfiguration(
            profile_identifier=self.profile_id,
        )

        try:
            with browser_session(
                region=self._region,
                profile_configuration=profile_config,
            ) as client:
                # browser_session always populates these; str() satisfies mypy
                # since the SDK types them as str | None
                self.bind_session(
                    browser_identifier=str(client.identifier),
                    session_id=str(client.session_id),
                )
                ws_url, headers = client.generate_ws_headers()
                _LOGGER.info(
                    "AgentCore browser session started: browser=%s, session=%s",
                    client.identifier,
                    client.session_id,
                )
                yield ws_url, headers
        except BrowserAuthError:
            raise
        except Exception as exc:
            raise BrowserAuthError(f"Failed to manage AgentCore browser session: {exc}") from exc
        finally:
            self._browser_identifier = None
            self._session_id = None

    # -----------------------------------------------------------------
    # BrowserSessionProvider overrides
    # -----------------------------------------------------------------

    def load_storage_state(self) -> StorageState | None:
        """Always returns ``None``.

        AgentCore restores browser state server-side when a session
        starts with a ``profileConfiguration``. No client-side state
        transfer is needed.
        """
        return None

    def load_cookies(self) -> list[SetCookieParam]:
        """Always returns an empty list.

        Cookies are restored server-side as part of the profile.
        """
        return []

    def save_session(self, state: StorageState) -> None:
        """Save browser state via the AgentCore data plane API.

        Calls ``SaveBrowserSessionProfile`` to persist state
        server-side. Unlike client-side providers, the provided
        ``state`` is ignored since persistence is handled
        server-side.

        Raises:
            BrowserAuthError: If session IDs are not bound or the
                API call fails.
        """
        self._save_profile_server_side()

    def save_storage_state(self, state: StorageState) -> None:
        """No-op. State is persisted server-side by ``save_session()``.

        The ``state`` dict is ignored. This method is called by the
        base class ``save_session()`` after ``context.storage_state()``,
        but the actual server-side save has already been done before
        that call.
        """

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    def _save_profile_server_side(self) -> None:
        """Call SaveBrowserSessionProfile on the data plane."""
        if not self._browser_identifier or not self._session_id:
            raise BrowserAuthError(
                "Cannot save AgentCore profile: session not bound. " "Call bind_session() or use cdp_session() first."
            )
        try:
            client = self._make_data_plane_client()
            client.save_browser_session_profile(
                profileIdentifier=self.profile_id,
                browserIdentifier=self._browser_identifier,
                sessionId=self._session_id,
            )
            _LOGGER.info("Saved AgentCore profile %s", self.profile_id)
        except BrowserAuthError:
            raise
        except Exception as exc:
            raise BrowserAuthError(f"Failed to save AgentCore profile {self.profile_id}: {exc}") from exc

    def _resolve_or_create_profile(self) -> str:
        """Resolve profile ID from cache, or create a new profile.

        1. Check local cache file.
        2. If cached, validate via GetBrowserProfile.
        3. If not cached or deleted, search by name via ListBrowserProfiles.
        4. If not found, create a new profile.
        5. Cache the profile ID locally.
        """
        # 1. Check local cache
        cached_id = self._load_cached_profile_id()
        if cached_id is not None:
            # 2. Validate it still exists
            if self._profile_exists(cached_id):
                _LOGGER.debug("Profile %s resolved from cache", cached_id)
                return cached_id
            _LOGGER.info(
                "Cached profile %s no longer exists",
                cached_id,
            )

        # 3. Search by name (handles cache loss, different machine, etc.)
        existing_id = self._find_profile_by_name(self._profile)
        if existing_id is not None:
            self._save_cached_profile_id(existing_id)
            _LOGGER.info("Found existing profile %s by name", existing_id)
            return existing_id

        # 4. Create new profile
        profile_id = self._create_profile()
        self._save_cached_profile_id(profile_id)
        _LOGGER.info("Created new AgentCore profile %s", profile_id)
        return profile_id

    def _create_profile(self) -> str:
        """Call CreateBrowserProfile on the control plane."""
        try:
            client = self._make_control_plane_client()
            response = client.create_browser_profile(
                name=self._profile,
                description=f"NovaAct session profile: {self._profile}",
            )
            return str(response["profileId"])
        except Exception as exc:
            raise BrowserAuthError(f"Failed to create AgentCore profile '{self._profile}': {exc}") from exc

    def _profile_exists(self, profile_id: str) -> bool:
        """Check if a profile exists and is usable."""
        try:
            client = self._make_control_plane_client()
            response = client.get_browser_profile(profileId=profile_id)
            status = response.get("status")
            return status in _USABLE_PROFILE_STATUSES
        except Exception:
            return False

    def _find_profile_by_name(self, name: str) -> str | None:
        """Search ListBrowserProfiles for a profile matching the name."""
        try:
            client = self._make_control_plane_client()
            next_token: str | None = None
            while True:
                kwargs: dict[str, object] = {"maxResults": 100}
                if next_token:
                    kwargs["nextToken"] = next_token
                response = client.list_browser_profiles(**kwargs)
                summaries = cast(
                    list[dict[str, object]],
                    response.get("profileSummaries", []),
                )
                for summary in summaries:
                    profile_name = str(summary.get("name", ""))
                    if profile_name == name and summary.get("status") in _USABLE_PROFILE_STATUSES:
                        return str(summary["profileId"])
                token = response.get("nextToken")
                next_token = str(token) if token is not None else None
                if not next_token:
                    break
        except Exception as exc:
            _LOGGER.warning("Failed to list browser profiles: %s", exc)
        return None

    def _load_cached_profile_id(self) -> str | None:
        """Load profile ID from local cache file."""
        try:
            text = self._cache_path.read_text(encoding="utf-8")
            data = json.loads(text)
            profile_id = data.get("profile_id")
            return str(profile_id) if profile_id is not None else None
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return None

    def _save_cached_profile_id(self, profile_id: str) -> None:
        """Save profile ID to local cache file.

        Writes atomically via a temp file and rename to prevent
        partial reads. File permissions are set to 0o600 (owner
        read/write only) to protect the profile ID from other
        users on the same machine.
        """
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            data = json.dumps(
                {"profile_id": profile_id, "name": self._profile},
                indent=2,
            )
            tmp_path = self._cache_path.with_suffix(".json.tmp")
            tmp_path.write_text(data, encoding="utf-8")
            os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)
            tmp_path.replace(self._cache_path)
            _LOGGER.debug("Cached profile ID at %s", self._cache_path)
        except Exception as exc:
            _LOGGER.warning(
                "Failed to cache profile ID at %s: %s",
                self._cache_path,
                exc,
            )

    def _make_control_plane_client(self) -> _ControlPlaneClient:
        """Create a boto3 control plane client."""
        import boto3

        return boto3.client(  # type: ignore[no-any-return]
            "bedrock-agentcore-control",
            region_name=self._region,
        )

    def _make_data_plane_client(self) -> _DataPlaneClient:
        """Create a boto3 data plane client."""
        import boto3

        return boto3.client(  # type: ignore[no-any-return]
            "bedrock-agentcore",
            region_name=self._region,
        )
