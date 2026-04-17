from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from collections import defaultdict
from threading import Condition, RLock
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


@dataclass(frozen=True, slots=True)
class StoredEvent:
    event_id: int
    event: BaseEvent
    created_at: datetime


class WorkflowEventStore:
    def __init__(self, max_events_per_session: int = 200) -> None:
        self.max_events_per_session = max(1, max_events_per_session)
        self._events: dict[str, list[StoredEvent]] = defaultdict(list)
        self._conditions: dict[str, Condition] = defaultdict(Condition)
        self._next_event_id: dict[str, int] = defaultdict(lambda: 1)
        self._lock = RLock()

    def append(self, session_id: str, event: BaseEvent) -> None:
        with self._lock:
            events = self._events[session_id]
            stored_event = StoredEvent(
                event_id=self._next_event_id[session_id],
                event=event,
                created_at=datetime.now(timezone.utc),
            )
            self._next_event_id[session_id] += 1
            events.append(stored_event)
            overflow = len(events) - self.max_events_per_session
            if overflow > 0:
                del events[:overflow]
            condition = self._conditions[session_id]
        with condition:
            condition.notify_all()

    def list_events(self, session_id: str) -> list[BaseEvent]:
        with self._lock:
            return [item.event for item in self._events.get(session_id, [])]

    def list_records(self, session_id: str, *, after_event_id: int = 0) -> list[StoredEvent]:
        with self._lock:
            return [
                item
                for item in self._events.get(session_id, [])
                if item.event_id > after_event_id
            ]

    def wait_for_events(
        self,
        session_id: str,
        *,
        after_event_id: int = 0,
        timeout_seconds: float = 15.0,
    ) -> list[StoredEvent]:
        records = self.list_records(session_id, after_event_id=after_event_id)
        if records:
            return records

        condition = self._conditions[session_id]
        with condition:
            condition.wait(timeout=timeout_seconds)

        return self.list_records(session_id, after_event_id=after_event_id)

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            self._events.pop(session_id, None)
            self._next_event_id.pop(session_id, None)
            condition = self._conditions.pop(session_id, None)
        if condition is not None:
            with condition:
                condition.notify_all()
