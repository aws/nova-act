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
from __future__ import annotations

import logging
import sys
import threading
import time
from collections import deque
from contextvars import ContextVar
from typing import NamedTuple, Type

from nova_act.util.logging import get_session_context

MAX_DOTS = 3


class QueuedLog(NamedTuple):
    message: str
    level: int


class Thinker:
    def __init__(self, tty: bool = True, logger: logging.Logger | None = None, prefix: str | None = None) -> None:
        self._stop_event = threading.Event()
        self._thread: threading.Thread
        self.logger = logger or logging.getLogger()
        self.prefix = prefix
        self.session_context = get_session_context()
        self.tty = tty

        # Create custom handler and formatter
        self.handler = logging.StreamHandler(sys.stdout)
        self.handler.terminator = ""
        self.formatter = logging.Formatter("%(message)s")
        self.handler.setFormatter(self.formatter)

        # Store original handlers to restore later
        self.original_handlers = self.logger.handlers

        # Queue of logs to emit
        self.logs_queue: deque[QueuedLog] = deque()

    def _make_prefix(self, *, with_state_emoji: bool) -> str:
        if self.prefix:
            return self.prefix
        elif self.session_context is not None:
            return self.session_context.trace_prefix(with_state_emoji=with_state_emoji)
        else:
            return ""

    def _print_dots(self) -> None:
        count = 1
        while not self._stop_event.is_set():
            prefix = self._make_prefix(with_state_emoji=True)
            prefix_without_emoji = self._make_prefix(with_state_emoji=False)
            clear_msg = f'\r{prefix}{" " * MAX_DOTS}'

            # If there are logs to process
            if self.logs_queue:
                # Get the log entry
                log_entry, log_level = self.logs_queue.popleft()
                # Clear line
                self.logger.info(clear_msg)
                # Print the log
                self.logger.log(log_level, f"\r{prefix_without_emoji}{log_entry}\n")

                # Print a fresh line with starting dot
                msg = f"{prefix}."  # No \r here since we're on a new line
                self.logger.info(msg)
                count = 1
            else:
                # Normal dot animation
                # Clear the line
                self.logger.info(clear_msg)
                # Print the new dots
                msg = f'\r{prefix}{"." * count}'
                self.logger.info(msg)
                count = (count % MAX_DOTS) + 1
                time.sleep(0.5)

    def __enter__(self) -> Thinker:
        self.logger.handlers = [self.handler]

        if self.tty:
            # Start the animated dots
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._print_dots)
            self._thread.start()
        else:
            # Just print three dots and return
            self.logger.info(f"{self._make_prefix(with_state_emoji=False)}...\n")

        _current_thinker.set(self)
        return self

    def __exit__(
        self, exc_type: Type[BaseException] | None, exc_value: BaseException | None, traceback: BaseException | None
    ) -> None:
        if self.tty:
            self._stop_event.set()
            self._thread.join()
            # Print final state and move to next line
            prefix = self._make_prefix(with_state_emoji=True)
            self.logger.info(f'\r{" " * (len(prefix) + MAX_DOTS)}\r{prefix}...\n')
        self.logger.handlers = self.original_handlers
        _current_thinker.set(None)

    def safe_log(self, message: str, level: int = logging.INFO) -> None:
        """Emit a log which does not interfere with the dots."""
        if self.tty:
            self.logs_queue.append(QueuedLog(message, level))
        else:
            self.logger.log(level, f"{self._make_prefix(with_state_emoji=False)}{message}\n")


_current_thinker = ContextVar[Thinker | None]("current_thinker", default=None)


def get_current_thinker() -> Thinker | None:
    return _current_thinker.get()
