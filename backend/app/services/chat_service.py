from __future__ import annotations

import asyncio
from copy import deepcopy

from app.core.errors import DrawAgentError, InputValidationError, ResourceConflictError
from app.graph import WorkflowEventStore, WorkflowRunner
from app.schemas.common import ErrorCode, StageName
from app.schemas.events import ErrorEvent
from app.services.session_service import SessionService
from app.services.task_manager import SessionTaskManager
from app.storage import SessionStore


class ChatService:
    def __init__(
        self,
        *,
        session_service: SessionService,
        session_store: SessionStore,
        workflow_runner: WorkflowRunner,
        event_store: WorkflowEventStore,
        task_manager: SessionTaskManager,
    ) -> None:
        self.session_service = session_service
        self.session_store = session_store
        self.workflow_runner = workflow_runner
        self.event_store = event_store
        self.task_manager = task_manager

    def run_workflow(
        self,
        *,
        session_id: str,
        request_id: str,
        source_text: str | None = None,
        user_feedback: str | None = None,
    ) -> str:
        active_operation = self.task_manager.active_operation(session_id)
        if active_operation is not None:
            raise ResourceConflictError(
                "Session already has an active background task.",
                details={"session_id": session_id, "active_operation": active_operation},
            )

        if bool(source_text) == bool(user_feedback):
            raise InputValidationError(
                "Exactly one run input must be provided.",
                details={"session_id": session_id},
            )
        operation = "run_source_text" if source_text is not None else "run_user_feedback"

        async def run_in_background() -> None:
            try:
                await asyncio.to_thread(
                    self.workflow_runner.run,
                    session_id,
                    request_id,
                    source_text=source_text,
                    user_feedback=user_feedback,
                )
            except Exception as exc:
                self._record_background_failure(session_id, request_id, exc)

        self.task_manager.start_task(
            session_id,
            operation=operation,
            request_id=request_id,
            coroutine=run_in_background(),
        )
        return operation

    def resume_workflow(
        self,
        *,
        session_id: str,
        request_id: str,
        user_feedback: str,
    ) -> str:
        active_operation = self.task_manager.active_operation(session_id)
        if active_operation is not None:
            raise ResourceConflictError(
                "Session already has an active background task.",
                details={"session_id": session_id, "active_operation": active_operation},
            )

        async def run_in_background() -> None:
            try:
                await asyncio.to_thread(
                    self.workflow_runner.resume,
                    session_id,
                    request_id,
                    user_feedback,
                )
            except Exception as exc:
                self._record_background_failure(session_id, request_id, exc)

        self.task_manager.start_task(
            session_id,
            operation="resume_user_feedback",
            request_id=request_id,
            coroutine=run_in_background(),
        )
        return "resume_user_feedback"

    def _record_background_failure(self, session_id: str, request_id: str, exc: Exception) -> None:
        try:
            record = self.session_store.get_session(session_id)
        except DrawAgentError:
            return

        state = deepcopy(record.state)
        state["stage"] = StageName.FAILED
        state["last_error"] = str(exc)
        state["needs_clarification"] = False
        state["interrupted"] = False
        self.session_store.update_state(session_id, state)

        error_code = (
            exc.error_code
            if isinstance(exc, DrawAgentError)
            else ErrorCode.INTERNAL_SERVER_ERROR
        )
        self.event_store.append(
            session_id,
            ErrorEvent(
                session_id=session_id,
                stage=StageName.FAILED,
                request_id=request_id,
                message="Workflow background execution failed.",
                error_code=error_code,
                details={"error": str(exc)},
            ),
        )
