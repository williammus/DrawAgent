from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import StreamingResponse

from app.api.deps import (
    get_chat_service,
    get_event_store,
    get_settings_from_app,
    get_session_service,
    get_task_manager,
)
from app.core.errors import SessionNotFoundError
from app.core.logging import get_request_id
from app.schemas import ChatResumeRequest, ChatRunRequest, ChatWorkflowResponse
from app.services import ChatService, SessionService, SessionTaskManager
from app.graph import WorkflowEventStore


router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/run", response_model=ChatWorkflowResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_workflow(
    payload: ChatRunRequest,
    request: Request,
    chat_service: ChatService = Depends(get_chat_service),
    session_service: SessionService = Depends(get_session_service),
) -> ChatWorkflowResponse:
    request_id = get_request_id()
    operation = chat_service.run_workflow(
        session_id=payload.session_id,
        request_id=request_id,
        source_text=payload.source_text,
        user_feedback=payload.user_feedback,
    )
    summary = session_service.get_summary(payload.session_id)
    return ChatWorkflowResponse(
        session_id=payload.session_id,
        stage=summary.stage,
        summary=summary,
        stream_url=f"/api/chat/stream/{payload.session_id}",
        operation=operation,
        response_message="Workflow request accepted.",
    )


@router.post("/resume", response_model=ChatWorkflowResponse, status_code=status.HTTP_202_ACCEPTED)
async def resume_workflow(
    payload: ChatResumeRequest,
    request: Request,
    chat_service: ChatService = Depends(get_chat_service),
    session_service: SessionService = Depends(get_session_service),
) -> ChatWorkflowResponse:
    request_id = get_request_id()
    operation = chat_service.resume_workflow(
        session_id=payload.session_id,
        request_id=request_id,
        user_feedback=payload.user_feedback,
    )
    summary = session_service.get_summary(payload.session_id)
    return ChatWorkflowResponse(
        session_id=payload.session_id,
        stage=summary.stage,
        summary=summary,
        stream_url=f"/api/chat/stream/{payload.session_id}",
        operation=operation,
        response_message="Clarification response accepted.",
    )


@router.get("/stream/{session_id}")
async def stream_session_events(
    session_id: str,
    request: Request,
    after_id: int = 0,
    once: bool = False,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    session_service: SessionService = Depends(get_session_service),
    event_store: WorkflowEventStore = Depends(get_event_store),
    task_manager: SessionTaskManager = Depends(get_task_manager),
) -> StreamingResponse:
    session_service.get_summary(session_id)
    heartbeat_seconds = get_settings_from_app(request).sse_heartbeat_seconds
    cursor = after_id
    if last_event_id:
        try:
            cursor = max(cursor, int(last_event_id))
        except ValueError:
            cursor = after_id

    async def event_stream():
        nonlocal cursor
        while True:
            if await request.is_disconnected():
                break

            records = await asyncio.to_thread(
                event_store.wait_for_events,
                session_id,
                after_event_id=cursor,
                timeout_seconds=float(heartbeat_seconds),
            )

            if records:
                for record in records:
                    cursor = record.event_id
                    payload = {
                        "event_id": record.event_id,
                        "event_type": record.event.event_type,
                        "data": record.event.model_dump(mode="json"),
                    }
                    yield (
                        f"id: {record.event_id}\n"
                        f"event: {record.event.event_type}\n"
                        f"data: {json.dumps(payload, ensure_ascii=True)}\n\n"
                    )
                if once:
                    break
                continue

            try:
                session_service.get_summary(session_id)
            except SessionNotFoundError:
                break

            if task_manager.active_operation(session_id) is None:
                yield ": keep-alive\n\n"
                if once:
                    break
            else:
                yield "event: heartbeat\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
