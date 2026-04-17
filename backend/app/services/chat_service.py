from __future__ import annotations

import asyncio
from copy import deepcopy

from app.core.errors import DrawAgentError, ResourceConflictError
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

    def submit_message(
        self,
        *,
        session_id: str,
        request_id: str,
        message: str,
        attachment_ids: list[str],
    ) -> str:
        active_operation = self.task_manager.active_operation(session_id)
        if active_operation is not None:
            raise ResourceConflictError(
                "Session already has an active background task.",
                details={"session_id": session_id, "active_operation": active_operation},
            )

        selected_files = self.session_service.resolve_attachments(session_id, attachment_ids)
        state = self.session_service.set_active_source_files(session_id, selected_files)
        operation = "resume_workflow" if state["interrupted"] else "run_workflow"

        async def run_in_background() -> None:
            try:
                if operation == "resume_workflow":
                    await asyncio.to_thread(
                        self.workflow_runner.resume,
                        session_id,
                        request_id,
                        message,
                    )
                else:
                    await asyncio.to_thread(
                        self.workflow_runner.run,
                        session_id,
                        request_id,
                        message,
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
