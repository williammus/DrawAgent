from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from uuid import uuid4

from app.core.errors import InputValidationError, SessionExpiredError, SessionNotFoundError
from app.graph.state import GraphState, build_initial_graph_state
from app.schemas.artifacts import SessionStateSummary


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class SessionRecord:
    session_id: str
    state: GraphState
    created_at: datetime
    updated_at: datetime
    expires_at: datetime

    def to_summary(self) -> SessionStateSummary:
        artifacts = self.state.get("artifacts") or {}
        return SessionStateSummary(
            session_id=self.session_id,
            stage=self.state["stage"],
            intent=self.state["intent"],
            has_source_text=bool(self.state.get("source_text")),
            source_text_locked=self.state.get("source_text_locked", False),
            has_logic_artifact=(
                artifacts.get("logic_artifact") is not None or self.state["payload_logic"] is not None
            ),
            has_style_artifact=(
                artifacts.get("style_artifact") is not None or self.state["payload_style"] is not None
            ),
            has_plan_review_artifact=artifacts.get("plan_review_artifact") is not None,
            has_mapper_artifact=(
                artifacts.get("mapper_artifact") is not None or self.state["payload_mapper"] is not None
            ),
            has_final_review_artifact=(
                artifacts.get("final_review_artifact") is not None or self.state["payload_review"] is not None
            ),
            has_final_prompt_artifact=(
                artifacts.get("final_prompt_artifact") is not None or self.state["payload_final"] is not None
            ),
            has_bypass_warning=bool(self.state.get("bypass_warnings")),
            needs_clarification=bool(
                self.state.get("pending_clarification") or self.state.get("needs_clarification")
            ),
            interrupted=self.state.get("interrupted", False),
            user_confirmed=self.state["user_confirmed"],
            error_count=self.state["error_count"],
            updated_at=self.updated_at,
            expires_at=self.expires_at,
        )


class SessionStore:
    def __init__(self, ttl_seconds: int) -> None:
        self._ttl_seconds = ttl_seconds
        self._records: dict[str, SessionRecord] = {}
        self._lock = RLock()

    def create_session(self, session_id: str | None = None, state: GraphState | None = None) -> SessionRecord:
        with self._lock:
            resolved_session_id = session_id or str(uuid4())
            if resolved_session_id in self._records:
                raise InputValidationError(
                    f"Session '{resolved_session_id}' already exists.",
                    details={"session_id": resolved_session_id},
                )

            now = utc_now()
            record = SessionRecord(
                session_id=resolved_session_id,
                state=state or build_initial_graph_state(resolved_session_id),
                created_at=now,
                updated_at=now,
                expires_at=now + timedelta(seconds=self._ttl_seconds),
            )
            self._records[resolved_session_id] = record
            return record

    def get_session(self, session_id: str) -> SessionRecord:
        with self._lock:
            record = self._records.get(session_id)
            if record is None:
                raise SessionNotFoundError(details={"session_id": session_id})
            if record.expires_at <= utc_now():
                del self._records[session_id]
                raise SessionExpiredError(details={"session_id": session_id})
            return record

    def get_state(self, session_id: str) -> GraphState:
        return self.get_session(session_id).state

    def update_state(self, session_id: str, state: GraphState) -> SessionRecord:
        with self._lock:
            record = self.get_session(session_id)
            now = utc_now()
            record.state = state
            record.updated_at = now
            record.expires_at = now + timedelta(seconds=self._ttl_seconds)
            return record

    def touch_session(self, session_id: str) -> SessionRecord:
        with self._lock:
            record = self.get_session(session_id)
            now = utc_now()
            record.updated_at = now
            record.expires_at = now + timedelta(seconds=self._ttl_seconds)
            return record

    def delete_session(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            return self._records.pop(session_id, None)

    def purge_expired(self, now: datetime | None = None) -> list[str]:
        with self._lock:
            reference_time = now or utc_now()
            expired_ids = [
                session_id
                for session_id, record in self._records.items()
                if record.expires_at <= reference_time
            ]
            for session_id in expired_ids:
                del self._records[session_id]
            return expired_ids

    def list_active_sessions(self) -> list[SessionStateSummary]:
        with self._lock:
            self.purge_expired()
            return [record.to_summary() for record in self._records.values()]

    def active_session_ids(self) -> set[str]:
        with self._lock:
            self.purge_expired()
            return set(self._records)
