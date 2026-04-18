from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

from langgraph.types import Command

from app.core.errors import InputValidationError
from app.graph.state import GraphState
from app.graph.stores import WorkflowCheckpointStore, WorkflowEventStore
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
        user_message: str | None = None,
    ) -> GraphState:
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
            user_message=user_message,
            has_checkpoint=bool(snapshot.values),
        )
        self.workflow_app.invoke(input_state, config=config)
        return self._sync_state(session_id, record.state, request_id)

    def resume(self, session_id: str, request_id: str, user_message: str) -> GraphState:
        record = self.session_store.get_session(session_id)
        config = self.checkpoint_store.config(session_id, request_id)
        snapshot = self.workflow_app.get_state(config)
        if not snapshot.next:
            raise InputValidationError(
                "Session is not waiting for clarification.",
                details={"session_id": session_id},
            )

        self.workflow_app.invoke(Command(resume=user_message), config=config)
        return self._sync_state(session_id, record.state, request_id)

    def get_state(self, session_id: str, request_id: str | None = None) -> GraphState:
        record = self.session_store.get_session(session_id)
        if request_id is None:
            return record.state

        config = self.checkpoint_store.config(session_id, request_id)
        snapshot = self.workflow_app.get_state(config)
        if not snapshot.values:
            return record.state
        return self._hydrate_state(record.state, snapshot.values)

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
        self.session_store.update_state(session_id, state)
        return state

    def _build_input_state(
        self,
        state: GraphState,
        *,
        user_message: str | None,
        has_checkpoint: bool,
    ) -> GraphState:
        working_state = cast(GraphState, deepcopy(state))
        if user_message is not None:
            message_field = self._select_message_field(working_state)
            working_state[message_field] = user_message
            working_state["last_error"] = None

        if has_checkpoint:
            working_state.pop("messages", None)

        return working_state

    def _select_message_field(self, state: GraphState) -> str:
        has_artifacts = any(
            state[field_name] is not None
            for field_name in (
                "payload_logic",
                "payload_style",
                "payload_mapper",
                "payload_review",
                "payload_final",
            )
        )
        if state["source_text"] or has_artifacts:
            return "user_feedback"
        return "source_text"

    def _hydrate_state(self, base_state: GraphState, values: dict[str, Any]) -> GraphState:
        hydrated = cast(GraphState, deepcopy(base_state))
        hydrated.update(values)
        return hydrated
