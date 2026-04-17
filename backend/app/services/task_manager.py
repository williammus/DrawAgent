from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Coroutine, Any

from app.core.errors import ResourceConflictError


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class SessionTaskRecord:
    session_id: str
    operation: str
    request_id: str
    task: asyncio.Task[None]
    created_at: datetime


class SessionTaskManager:
    def __init__(self) -> None:
        self._tasks: dict[str, SessionTaskRecord] = {}
        self._lock = RLock()

    def start_task(
        self,
        session_id: str,
        *,
        operation: str,
        request_id: str,
        coroutine: Coroutine[Any, Any, None],
    ) -> SessionTaskRecord:
        with self._lock:
            current = self._tasks.get(session_id)
            if current is not None and not current.task.done():
                raise ResourceConflictError(
                    "Session already has an active background task.",
                    details={
                        "session_id": session_id,
                        "active_operation": current.operation,
                    },
                )

            task = asyncio.create_task(coroutine)
            record = SessionTaskRecord(
                session_id=session_id,
                operation=operation,
                request_id=request_id,
                task=task,
                created_at=utc_now(),
            )
            self._tasks[session_id] = record
            task.add_done_callback(lambda _: self._clear_if_current(record))
            return record

    def active_operation(self, session_id: str) -> str | None:
        with self._lock:
            current = self._tasks.get(session_id)
            if current is None or current.task.done():
                return None
            return current.operation

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            current = self._tasks.pop(session_id, None)
        if current is not None and not current.task.done():
            current.task.cancel()

    def cancel_all(self) -> None:
        with self._lock:
            session_ids = list(self._tasks)
        for session_id in session_ids:
            self.clear_session(session_id)

    def _clear_if_current(self, record: SessionTaskRecord) -> None:
        with self._lock:
            current = self._tasks.get(record.session_id)
            if current is record:
                self._tasks.pop(record.session_id, None)
