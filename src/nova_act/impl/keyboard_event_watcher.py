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
import threading
from typing import Any, Literal

from nova_act.util.terminal_manager import TerminalInputManager


class KeyboardEventWatcher:
    """
    Helper class for allowing user keystrokes to be monitored on a non-blocking thread.

    Use as follows:

    with KeyboardEventWatcher("<key(s) to watch>", "<message>") as watcher:
        if watcher.is_triggered():
            do_something()
        watcher.reset()  # if you need to reuse the watcher
    """

    key: str
    trigger: threading.Event
    watcher_thread: threading.Thread | None
    final_stop: bool
    terminal_manager: TerminalInputManager

    def __init__(self, key: str, human_readable_key: str, message: str):
        self.key = key
        self.trigger = threading.Event()
        self.final_stop = False
        self.watcher_thread = None

    def _watch_for_trigger(self) -> None:
        while not self.final_stop:
            key = self.terminal_manager.get_char(block=False)
            if self.key == key:
                if self.trigger.is_set():
                    continue
                self.trigger.set()

    def __enter__(self) -> "KeyboardEventWatcher":
        """Override terminal and start new thread when watcher is entered."""
        self.terminal_manager = TerminalInputManager().__enter__()

        # Start the watcher thread
        self.watcher_thread = threading.Thread(target=self._watch_for_trigger, daemon=True)
        self.watcher_thread.start()

        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Literal[False]:
        """Clean up the watcher thread and reset terminal when exiting the context."""
        if self.terminal_manager:
            self.terminal_manager.__exit__(exc_type, exc_val, exc_tb)

        self.final_stop = True
        if self.watcher_thread and self.watcher_thread.is_alive():
            self.watcher_thread.join()
        return False  # Don't suppress any exceptions

    def is_triggered(self) -> bool:
        return self.trigger.is_set()

    def reset(self) -> None:
        self.trigger.clear()
