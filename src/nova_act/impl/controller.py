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

import threading
from contextlib import nullcontext
from enum import Enum, auto
from types import TracebackType
from typing import Optional, Type

from nova_act.impl.keyboard_event_watcher import KeyboardEventWatcher


class ControlState(Enum):
    ACTIVE = auto()
    PAUSED = auto()
    CANCELLED = auto()


class NovaStateController:
    def __init__(self, tty: bool) -> None:
        self._keyboard_manager = (
            KeyboardEventWatcher(chr(24), "ctrl+x", "stop agent act() call without quitting the browser")
            if tty
            else nullcontext()
        )
        self._state = ControlState.ACTIVE
        self._lock = threading.Lock()

    @property
    def state(self) -> ControlState:
        with self._lock:
            if isinstance(self._keyboard_manager, KeyboardEventWatcher) and self._keyboard_manager.is_triggered():
                if self._state != ControlState.CANCELLED:
                    self._state = ControlState.CANCELLED
            return self._state

    def pause(self) -> None:
        with self._lock:
            if self._state != ControlState.ACTIVE:
                raise RuntimeError(f"Cannot pause when state is {self._state}")
            self._state = ControlState.PAUSED

    def resume(self) -> None:
        with self._lock:
            if self._state != ControlState.PAUSED:
                raise RuntimeError(f"Cannot resume when state is {self._state}")
            self._state = ControlState.ACTIVE

    def cancel(self) -> None:
        with self._lock:
            self._state = ControlState.CANCELLED

    def reset(self) -> None:
        with self._lock:
            if isinstance(self._keyboard_manager, KeyboardEventWatcher):
                self._keyboard_manager.reset()
            self._state = ControlState.ACTIVE

    def __enter__(self) -> NovaStateController:
        try:
            self._keyboard_manager.__enter__()
        finally:
            self.reset()

        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        try:
            self._keyboard_manager.__exit__(exc_type, exc_val, exc_tb)
        finally:
            self.reset()
