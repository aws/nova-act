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
"""NovaAct instance initialization and connection management."""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

from nova_act import NovaAct
from nova_act.cli.browser.services.session.chrome_terminator import ChromeTerminator
from nova_act.cli.browser.services.session.models import (
    SessionInfo,
    SessionState,
)
from nova_act.cli.browser.services.session.persistence import SessionPersistence
from nova_act.cli.browser.utils.auth import AuthConfig, AuthMode
from nova_act.cli.browser.utils.log_capture import get_log_dir, suppress_sdk_output
from nova_act.cli.core.output import is_verbose_mode
from nova_act.cli.core.process import is_process_running
from nova_act.types.workflow import BotoSessionKwargs

if TYPE_CHECKING:
    from nova_act.types.workflow import Workflow

logger = logging.getLogger(__name__)


def _build_boto_kwargs(auth_config: AuthConfig) -> BotoSessionKwargs:
    """Build boto3.Session kwargs from AuthConfig."""
    kwargs = BotoSessionKwargs()
    if auth_config.profile:
        kwargs["profile_name"] = auth_config.profile
    if auth_config.region:
        kwargs["region_name"] = auth_config.region
    return kwargs


class NovaActConnector:
    """Handles NovaAct instance initialization and browser connection."""

    def __init__(
        self,
        persistence: SessionPersistence,
        chrome_terminator: ChromeTerminator,
    ) -> None:
        """Initialize connector with injected dependencies.

        Args:
            persistence: Session metadata persistence
            chrome_terminator: Chrome process terminator
        """
        self._persistence = persistence
        self._chrome_terminator = chrome_terminator
        self._exit_stack: contextlib.ExitStack | None = None

    def connect_to_session(
        self,
        session_info: SessionInfo,
        starting_page: str | None,
        nova_args: dict[str, object],
        auth_config: AuthConfig | None = None,
    ) -> None:
        """Initialize and start NovaAct instance for session.

        Args:
            session_info: Session to connect NovaAct to
            starting_page: Optional URL to navigate to
            nova_args: Additional NovaAct constructor arguments
            auth_config: Authentication configuration (None defaults to api-key behavior)

        Raises:
            RuntimeError: If NovaAct start fails
        """
        nova_act: NovaAct | None = None
        try:
            constructor_args = self._build_constructor_args(session_info, nova_args, auth_config)
            nova_act = self._initialize(constructor_args)
            self._navigate_to_starting_page(nova_act, starting_page)

            session_info.nova_act_instance = nova_act
            session_info.state = SessionState.STARTED
        except Exception as e:  # noqa: BLE001 — session connection error boundary; multiple heterogeneous operations
            if nova_act is not None:
                with contextlib.suppress(Exception):
                    nova_act.stop()
            self.cleanup_workflow()
            self._handle_failure(session_info, e)
            raise RuntimeError(f"Failed to start session '{session_info.session_id}': {e}") from e

    def reconnect_to_session(
        self,
        session_info: SessionInfo,
        auth_config: AuthConfig | None = None,
    ) -> None:
        """Reconnect to existing browser session.

        Args:
            session_info: Session to reconnect
            auth_config: Authentication configuration (None defaults to api-key behavior)

        Raises:
            RuntimeError: If reconnection fails
        """
        nova_act: NovaAct | None = None
        try:
            constructor_args = self._build_constructor_args(session_info, {}, auth_config)
            nova_act = self._initialize(constructor_args)
            session_info.nova_act_instance = nova_act
            session_info.state = SessionState.STARTED
        except Exception as e:  # noqa: BLE001 — session reconnection error boundary; multiple heterogeneous operations
            self.cleanup_workflow()
            self._handle_failure(session_info, e)
            sid = session_info.session_id
            cleanup_hint = f"Clean up with: act browser session close --force --session-id {sid}"
            if session_info.browser_pid is not None and not is_process_running(session_info.browser_pid):
                diagnosis = "browser was closed externally"
            else:
                diagnosis = "browser is unresponsive (CDP endpoint not reachable)"
            raise RuntimeError(f"Failed to reconnect to session '{sid}': {diagnosis}. {cleanup_hint}") from e

    def _build_constructor_args(
        self,
        session_info: SessionInfo,
        nova_args: dict[str, object],
        auth_config: AuthConfig | None = None,
    ) -> dict[str, object]:
        """Build NovaAct constructor arguments.

        All sessions connect via CDP endpoint to a CLI-launched Chrome instance.

        For api-key mode (or no auth_config): NovaAct reads env var.
        For aws mode: ensures workflow definition exists, creates a Workflow, enters it,
        and passes it to NovaAct.

        Args:
            session_info: Session metadata
            nova_args: Additional NovaAct constructor arguments
            auth_config: Authentication configuration
        """
        args = self._build_base_args(session_info, nova_args)

        if auth_config and auth_config.mode == AuthMode.AWS:
            args["workflow"] = self._setup_aws_workflow(auth_config)

        return args

    @staticmethod
    def _build_base_args(session_info: SessionInfo, nova_args: dict[str, object]) -> dict[str, object]:
        """Build common NovaAct constructor arguments (CDP connection, logging, browser options)."""
        browser_opts = session_info.browser_options_meta
        ignore_https = browser_opts.get("ignore_https_errors", False) if isinstance(browser_opts, dict) else False
        log_dir = get_log_dir(session_info.session_id)
        log_dir.mkdir(parents=True, exist_ok=True)
        args: dict[str, object] = {
            "ignore_https_errors": ignore_https,
            "logs_directory": str(log_dir),
            "tty": False,
            "cdp_endpoint_url": session_info.cdp_endpoint,
            "cdp_use_existing_page": True,
            **nova_args,
        }
        return args

    def _setup_aws_workflow(self, auth_config: AuthConfig) -> Workflow:
        """Create and enter an AWS Workflow context for authenticated NovaAct usage.

        Args:
            auth_config: AWS authentication configuration

        Returns:
            The entered Workflow instance
        """
        from nova_act.types.workflow import Workflow  # noqa: PLC0415

        boto_kwargs = _build_boto_kwargs(auth_config)
        workflow_name = auth_config.workflow_name or "act-cli"
        self._ensure_workflow_definition(workflow_name, boto_kwargs)

        wf = Workflow(
            model_id="nova-act-latest",
            boto_session_kwargs=boto_kwargs,
            workflow_definition_name=workflow_name,
        )
        stack = contextlib.ExitStack()
        stack.enter_context(wf)  # type: ignore[arg-type]  # Workflow implements __enter__/__exit__
        self._exit_stack = stack
        return wf

    def cleanup_workflow(self) -> None:
        """Clean up active Workflow context if one exists."""
        if self._exit_stack is not None:
            try:
                self._exit_stack.close()
            except Exception:  # noqa: BLE001 — cleanup boundary; must not let workflow teardown failures propagate
                logger.debug("Failed to clean up workflow", exc_info=True)
            finally:
                self._exit_stack = None

    @staticmethod
    def _ensure_workflow_definition(workflow_name: str, boto_kwargs: BotoSessionKwargs) -> None:
        """Create workflow definition in AWS if it doesn't exist.

        Idempotent — silently succeeds if the definition already exists (ConflictException).
        Logs a warning and continues on other failures, letting the SDK surface its own error.
        """
        try:
            from boto3 import Session as BotoSession  # noqa: PLC0415
            from botocore.exceptions import ClientError  # noqa: PLC0415

            from nova_act.cli.core.clients.nova_act.client import NovaActClient  # noqa: PLC0415
            from nova_act.cli.core.clients.nova_act.types import CreateWorkflowDefinitionRequest  # noqa: PLC0415
        except ImportError:
            logger.debug("boto3 or nova_act client not available — skipping workflow definition auto-creation")
            return

        try:
            session = BotoSession(**boto_kwargs)  # type: ignore[arg-type]
            client = NovaActClient(boto_session=session, region_name=boto_kwargs.get("region_name", "us-east-1"))
            client.create_workflow_definition(
                CreateWorkflowDefinitionRequest(name=workflow_name, description="Created by act browser CLI")
            )
            logger.info("Created workflow definition '%s'", workflow_name)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ConflictException":
                logger.debug("Workflow definition '%s' already exists", workflow_name)
            else:
                logger.warning("Could not auto-create workflow definition '%s': %s", workflow_name, e)
        except (
            Exception
        ) as e:  # noqa: BLE001 — fallback after specific ClientError handler; catches any non-ClientError from boto/SDK
            logger.warning("Could not auto-create workflow definition '%s': %s", workflow_name, e)

    def _initialize(self, constructor_args: dict[str, object]) -> NovaAct:
        """Initialize and start NovaAct instance.

        Suppresses SDK stdout/stderr noise (trace logs, thinker dots) unless verbose mode is active.
        This is the single point where all NovaAct instances are created, so suppression here
        covers all commands (create, close, close-all, and any prepare_session-based command).
        """
        if is_verbose_mode():
            nova_act = NovaAct(**constructor_args)  # type: ignore[arg-type]
            nova_act.start()
        else:
            with suppress_sdk_output():
                nova_act = NovaAct(**constructor_args)  # type: ignore[arg-type]
                nova_act.start()
        return nova_act

    def _navigate_to_starting_page(self, nova_act: NovaAct, starting_page: str | None) -> None:
        """Navigate to starting page if provided."""
        if starting_page and starting_page != "about:blank":
            nova_act.go_to_url(starting_page)

    def _handle_failure(self, session_info: SessionInfo, error: Exception) -> None:
        """Handle NovaAct initialization failure."""
        self._chrome_terminator.terminate(session_info.browser_pid)
        session_info.state = SessionState.FAILED
        session_info.error_message = str(error)
        self._persistence.write_session_metadata(session_info)
