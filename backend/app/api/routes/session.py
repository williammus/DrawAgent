from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import get_session_service
from app.schemas import CleanupReport, SessionDeleteResponse, SessionInitResponse
from app.services import SessionService


router = APIRouter(prefix="/api/session", tags=["session"])


@router.post("/init", response_model=SessionInitResponse, status_code=status.HTTP_201_CREATED)
async def init_session(
    session_service: SessionService = Depends(get_session_service),
) -> SessionInitResponse:
    summary = session_service.create_session()
    return SessionInitResponse(session_id=summary.session_id, summary=summary)


@router.delete("/{session_id}", response_model=SessionDeleteResponse)
async def delete_session(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
) -> SessionDeleteResponse:
    deleted, removed_directory = session_service.delete_session(session_id)
    cleanup = CleanupReport(
        removed_sessions=[session_id] if deleted else [],
        removed_directories=[session_id] if removed_directory else [],
    )
    return SessionDeleteResponse(
        session_id=session_id,
        deleted=deleted,
        cleanup=cleanup,
    )
