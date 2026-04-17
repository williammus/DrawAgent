from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_session_service
from app.schemas import ArtifactResponse
from app.services import SessionService


router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


@router.get("/{session_id}", response_model=ArtifactResponse)
async def get_artifacts(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
) -> ArtifactResponse:
    return session_service.get_artifacts(session_id)
