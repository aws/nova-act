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
"""Log tailing functionality for AgentCore workflows."""

import logging
import threading
from dataclasses import dataclass
from typing import Callable, TypedDict

from boto3 import Session

from nova_act.cli.core.identity import auto_detect_account_id

logger = logging.getLogger(__name__)


@dataclass
class LogEvent:
    message: str
    timestamp: int  # milliseconds since epoch


class LogEventData(TypedDict):
    message: str
    timestamp: str


class SessionUpdateData(TypedDict):
    sessionResults: list[LogEventData]


@dataclass
class CloudWatchEvent:
    """CloudWatch log event structure."""

    events: dict[str, SessionUpdateData]


class LogTailer:
    def __init__(self, session: Session | None, region: str, log_group: str):
        self.region = region
        self.log_group = log_group
        self.session = session or Session()
        self.logs_client = self.session.client("logs", region_name=region)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, callback: Callable[[LogEvent], None]) -> None:
        """Start tailing logs from CloudWatch."""
        self._stop_event.clear()  # Clear event when starting
        self._thread = threading.Thread(target=self._tail, args=(callback,), daemon=True)
        self._thread.start()

    def _get_log_group_arn(self) -> str:
        """Convert log group name to ARN format required by start_live_tail."""
        account_id = auto_detect_account_id(self.session, self.region)
        return f"arn:aws:logs:{self.region}:{account_id}:log-group:{self.log_group}"

    def _tail(self, callback: Callable[[LogEvent], None]) -> None:
        try:
            log_group_arn = self._get_log_group_arn()
            event_stream = self._start_live_tail_stream(log_group_arn)
            self._process_event_stream(event_stream=event_stream, callback=callback)
        except Exception as e:
            logger.error(msg=f"Log tailing failed: {e}")

    def _process_events(self, event: CloudWatchEvent, callback: Callable[[LogEvent], None]) -> None:
        """Process a single event from the log stream."""
        if "sessionStart" in event.events:
            return
        elif "sessionUpdate" in event.events:
            log_events = event.events["sessionUpdate"]["sessionResults"]
            for log_event in log_events:
                callback(LogEvent(message=log_event["message"], timestamp=int(log_event["timestamp"])))
        else:
            logger.warning(msg=f"Unknown event type received: {event}")

    def stop(self) -> None:
        self._stop_event.set()

    def __enter__(self) -> "LogTailer":
        """Enter context manager - return self for use in with statement."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Exit context manager - ensure log tailer is stopped."""
        self.stop()

    def _start_live_tail_stream(self, log_group_arn: str):  # type: ignore[no-untyped-def]
        """Start live tail stream and return event stream."""
        logger.debug(msg=f"Starting live tail for log group ARN: {log_group_arn}")
        response = self.logs_client.start_live_tail(logGroupIdentifiers=[log_group_arn])
        event_stream = response["responseStream"]
        logger.debug(msg="Live tail stream established")
        return event_stream

    def _process_event_stream(  # type: ignore[no-untyped-def]
        self, event_stream, callback: Callable[[LogEvent], None]
    ) -> None:
        """Process events from the live tail stream."""
        for event in event_stream:
            if self._stop_event.is_set():
                logger.debug(msg="Stop event set, closing stream")
                event_stream.close()
                break

            logger.debug(msg=f"Received event: {event}")
            self._process_events(event=CloudWatchEvent(events=event), callback=callback)
