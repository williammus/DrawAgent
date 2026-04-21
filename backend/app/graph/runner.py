from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

from langgraph.types import Command

from app.core.errors import InputValidationError
from app.graph.state import GraphState
from app.graph.stores import WorkflowCheckpointStore, WorkflowEventStore
from app.schemas import ClarificationRequestSpec, StageName
from app.schemas.events import ClarificationRequiredEvent
from app.storage.session_store import SessionStore


class WorkflowRunner:
    def __init__(
        self,
        *,
        workflow_app: Any,
        session_store: SessionStore,
        checkpoint_store: WorkflowCheckpointStore,
        event_store: WorkflowEventStore,
    ) -> None:
        self.workflow_app = workflow_app
        self.session_store = session_store
        self.checkpoint_store = checkpoint_store
        self.event_store = event_store

    def run(
        self,
        session_id: str,
        request_id: str,
        *,
        source_text: str | None = None,
        user_feedback: str | None = None,
    ) -> GraphState:
        if bool(source_text) == bool(user_feedback):
            raise InputValidationError(
                "Exactly one of source_text or user_feedback must be provided.",
                details={"session_id": session_id},
            )

        record = self.session_store.get_session(session_id)
        config = self.checkpoint_store.config(session_id, request_id)
        snapshot = self.workflow_app.get_state(config)
        if snapshot.next:
            raise InputValidationError(
                "Session is waiting for clarification. Use resume() to continue.",
                details={"session_id": session_id},
            )

        input_state = self._build_input_state(
            record.state,
            source_text=source_text,
            user_feedback=user_feedback,
            has_checkpoint=bool(snapshot.values),
        )
        self.workflow_app.invoke(input_state, config=config)
        return self._sync_state(session_id, record.state, request_id)

    def resume(self, session_id: str, request_id: str, *, user_feedback: str) -> GraphState:
        record = self.session_store.get_session(session_id)
        config = self.checkpoint_store.config(session_id, request_id)
        snapshot = self.workflow_app.get_state(config)
        if not snapshot.next:
            raise InputValidationError(
                "Session is not waiting for clarification.",
                details={"session_id": session_id},
            )

        self.workflow_app.invoke(Command(resume=user_feedback), config=config)
        return self._sync_state(session_id, record.state, request_id)

    def is_waiting_for_resume(self, session_id: str) -> bool:
        snapshot = self.workflow_app.get_state(self.checkpoint_store.config(session_id))
        return bool(snapshot.next)

    def get_state(self, session_id: str, request_id: str | None = None) -> GraphState:
        record = self.session_store.get_session(session_id)
        config = self.checkpoint_store.config(session_id, request_id)
        snapshot = self.workflow_app.get_state(config)
        if not snapshot.values:
            hydrated = record.state
        else:
            hydrated = self._hydrate_state(record.state, snapshot.values)

        if snapshot.next:
            return self._apply_interrupted_snapshot(session_id, hydrated)
        return hydrated

    def clear_session(self, session_id: str) -> None:
        self.event_store.clear_session(session_id)
        self.checkpoint_store.clear_session(session_id)

    def _sync_state(
        self,
        session_id: str,
        base_state: GraphState,
        request_id: str,
    ) -> GraphState:
        config = self.checkpoint_store.config(session_id, request_id)
        snapshot = self.workflow_app.get_state(config)
        state = self._hydrate_state(base_state, snapshot.values)
        if snapshot.next:
            state = self._apply_interrupted_snapshot(session_id, state)
        self.session_store.update_state(session_id, state)
        return state

    def _build_input_state(
        self,
        state: GraphState,
        *,
        source_text: str | None,
        user_feedback: str | None,
        has_checkpoint: bool,
    ) -> GraphState:
        working_state = cast(GraphState, deepcopy(state))
        if source_text is not None:
            if working_state["source_text"] is not None:
                raise InputValidationError(
                    "source_text is read-only after the first submission.",
                    details={"session_id": working_state["session_id"]},
                )
            working_state["source_text"] = source_text

        if user_feedback is not None:
            if working_state["source_text"] is None:
                raise InputValidationError(
                    "user_feedback requires source_text to exist first.",
                    details={"session_id": working_state["session_id"]},
                )
            working_state["user_feedback"] = user_feedback

        working_state["last_error"] = None
        if has_checkpoint:
            working_state.pop("messages", None)
        return working_state

    def _hydrate_state(self, base_state: GraphState, values: dict[str, Any]) -> GraphState:
        hydrated = cast(GraphState, deepcopy(base_state))
        hydrated.update(values)
        return hydrated

    def _apply_interrupted_snapshot(self, session_id: str, state: GraphState) -> GraphState:
        clarification_event = self._latest_clarification_event(session_id)
        if clarification_event is None:
            state["stage"] = StageName.CLARIFYING
            state["needs_clarification"] = True
            state["interrupted"] = True
            return state

        state["stage"] = StageName.CLARIFYING
        state["needs_clarification"] = True
        state["interrupted"] = True
        state["active_clarification"] = ClarificationRequestSpec(
            question=clarification_event.clarification_question,
            reason=clarification_event.reason or "",
            expected_fields=clarification_event.expected_fields,
        )
        return state

    def _latest_clarification_event(self, session_id: str) -> ClarificationRequiredEvent | None:
        for event in reversed(self.event_store.list_events(session_id)):
            if isinstance(event, ClarificationRequiredEvent):
                return event
        return None
