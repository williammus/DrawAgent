from __future__ import annotations

from collections import defaultdict
from threading import RLock
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from app.schemas.events import BaseEvent


class WorkflowCheckpointStore:
    def __init__(self, saver: InMemorySaver | None = None) -> None:
        self.saver = saver or InMemorySaver()

    def config(self, session_id: str, request_id: str | None = None) -> dict[str, Any]:
        configurable: dict[str, Any] = {"thread_id": session_id}
        if request_id is not None:
            configurable["request_id"] = request_id
        return {"configurable": configurable}

    def clear_session(self, session_id: str) -> None:
        self.saver.delete_thread(session_id)


class WorkflowEventStore:
    def __init__(self, max_events_per_session: int = 200) -> None:
        self.max_events_per_session = max(1, max_events_per_session)
        self._events: dict[str, list[BaseEvent]] = defaultdict(list)
        self._lock = RLock()

    def append(self, session_id: str, event: BaseEvent) -> None:
        with self._lock:
            events = self._events[session_id]
            events.append(event)
            overflow = len(events) - self.max_events_per_session
            if overflow > 0:
                del events[:overflow]

    def list_events(self, session_id: str) -> list[BaseEvent]:
        with self._lock:
            return list(self._events.get(session_id, []))

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            self._events.pop(session_id, None)
