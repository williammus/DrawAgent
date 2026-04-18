from __future__ import annotations

import asyncio
import logging
from copy import deepcopy

from app.core.errors import DrawAgentError, InputValidationError, ResourceConflictError
from app.graph import WorkflowEventStore
from app.image import BaseImageAdapter
from app.schemas.common import ErrorCode, GenerateStatus, StageName
from app.schemas.events import ErrorEvent, ImageGeneratedEvent, StageCompletedEvent, StageStartedEvent
from app.services.task_manager import SessionTaskManager
from app.storage import SessionStore


logger = logging.getLogger(__name__)


class GenerationService:
    def __init__(
        self,
        *,
        session_store: SessionStore,
        event_store: WorkflowEventStore,
        image_adapter: BaseImageAdapter,
        task_manager: SessionTaskManager,
    ) -> None:
        self.session_store = session_store
        self.event_store = event_store
        self.image_adapter = image_adapter
        self.task_manager = task_manager

    def start_generation(self, *, session_id: str, request_id: str) -> GenerateStatus:
        active_operation = self.task_manager.active_operation(session_id)
        if active_operation is not None:
            raise ResourceConflictError(
                "Session already has an active background task.",
                details={"session_id": session_id, "active_operation": active_operation},
            )

        record = self.session_store.get_session(session_id)
        payload_final = record.state["payload_final"]
        if payload_final is None or not payload_final.ready_for_generation:
            raise InputValidationError(
                "Session does not have a confirmed final prompt ready for image generation.",
                details={"session_id": session_id},
            )

        state = deepcopy(record.state)
        state["user_confirmed"] = True
        state["stage"] = StageName.GENERATING_IMAGE
        state["last_error"] = None
        self.session_store.update_state(session_id, state)

        async def run_in_background() -> None:
            try:
                await asyncio.to_thread(
                    self._generate_sync,
                    session_id,
                    request_id,
                    payload_final.final_prompt_en,
                )
            except Exception as exc:
                self._record_generation_failure(session_id, request_id, exc)

        self.task_manager.start_task(
            session_id,
            operation="generate_image",
            request_id=request_id,
            coroutine=run_in_background(),
        )
        return GenerateStatus.ACCEPTED

    def _generate_sync(self, session_id: str, request_id: str, prompt_text: str) -> None:
        logger.info(
            "Starting image generation: session_id=%s request_id=%s image_provider=%s image_model=%s",
            session_id,
            request_id,
            self.image_adapter.provider_name,
            getattr(self.image_adapter, "model", None),
        )
        self.event_store.append(
            session_id,
            StageStartedEvent(
                session_id=session_id,
                stage=StageName.GENERATING_IMAGE,
                request_id=request_id,
                message="Image generation started.",
            ),
        )
        relative_path, image_meta = self.image_adapter.generate(session_id, prompt_text)
        record = self.session_store.get_session(session_id)
        state = deepcopy(record.state)
        state["stage"] = StageName.COMPLETED
        state["last_error"] = None
        state["generated_image_path"] = relative_path
        state["generated_image_meta"] = image_meta
        state["user_confirmed"] = True
        self.session_store.update_state(session_id, state)
        self.event_store.append(
            session_id,
            StageCompletedEvent(
                session_id=session_id,
                stage=StageName.GENERATING_IMAGE,
                request_id=request_id,
                message="Image generation completed.",
            ),
        )
        self.event_store.append(
            session_id,
            ImageGeneratedEvent(
                session_id=session_id,
                stage=StageName.COMPLETED,
                request_id=request_id,
                message="Image generated successfully.",
                image_path=relative_path,
            ),
        )

    def _record_generation_failure(self, session_id: str, request_id: str, exc: Exception) -> None:
        try:
            record = self.session_store.get_session(session_id)
        except DrawAgentError:
            return

        state = deepcopy(record.state)
        state["stage"] = StageName.FAILED
        state["last_error"] = str(exc)
        self.session_store.update_state(session_id, state)
        error_code = (
            exc.error_code
            if isinstance(exc, DrawAgentError)
            else ErrorCode.INTERNAL_SERVER_ERROR
        )
        error_details = {"error": str(exc)}
        if isinstance(exc, DrawAgentError) and isinstance(exc.details, dict):
            error_details.update(exc.details)
        provider = getattr(self.image_adapter, "provider_name", None)
        model = getattr(self.image_adapter, "model", None)
        if provider:
            error_details["provider"] = provider
        if model:
            error_details["model"] = model
        self.event_store.append(
            session_id,
            ErrorEvent(
                session_id=session_id,
                stage=StageName.FAILED,
                request_id=request_id,
                message="Image generation failed.",
                error_code=error_code,
                details=error_details,
            ),
        )
