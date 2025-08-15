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
from typing import Callable

from nova_act.types.events import (
    ActionData,
    Event,
    EventContext,
    EventType,
    LogData,
    LogType,
)
from nova_act.types.state.act import Act
from nova_act.util.logging import get_session_id

NovaEventCallback = Callable[[Event], None]


class EventHandler:
    def __init__(self, callback: NovaEventCallback | None):
        self._callback = callback
        self._act: Act | None = None

    def set_act(self, act: Act) -> None:
        self._act = act

    def build_context(self, **kwargs: object) -> EventContext:
        data = kwargs.get("data")
        return EventContext(
            session_id=get_session_id(),
            act_id=self._act.id if self._act else None,
            num_steps_executed=len(self._act._steps) if self._act else None,
            payload_type=type(data).__name__ if data is not None else None,
            is_complete=self._act.is_complete if self._act else False,
        )

    def build_data(self, *, event_type: EventType, **kwargs: object) -> ActionData | LogData:
        match event_type:
            case EventType.ACTION:
                return ActionData(
                    action=str(kwargs.get("action", "unknown")),
                    data=kwargs.get("data", ""),
                )
            case EventType.LOG:
                log_level = kwargs.get("log_level", LogType.INFO)
                if not isinstance(log_level, LogType):
                    raise TypeError(f"log_level must be a LogType, got {type(log_level).__name__}")
                return LogData(log_level=log_level, data=str(kwargs.get("data", "")))
            case _:
                raise ValueError(f"Unsupported EventType: {type}")

    def send_event(self, *, type: EventType, **kwargs: object) -> None:
        if self._callback is None:
            return
        event_data = self.build_data(event_type=type, **kwargs)
        event_context = self.build_context(**kwargs)
        event = Event(type=type, data=event_data, context=event_context)
        self._callback(event)
