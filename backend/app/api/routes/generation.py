from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse

from app.api.deps import get_generation_service, get_session_service
from app.core.logging import get_request_id
from app.schemas import GenerateResponse
from app.services import GenerationService, SessionService


router = APIRouter(tags=["generation"])


@router.post("/api/generate/{session_id}", response_model=GenerateResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_image(
    session_id: str,
    generation_service: GenerationService = Depends(get_generation_service),
    session_service: SessionService = Depends(get_session_service),
) -> GenerateResponse:
    generation_status = generation_service.start_generation(
        session_id=session_id,
        request_id=get_request_id(),
    )
    summary = session_service.get_summary(session_id)
    return GenerateResponse(
        session_id=session_id,
        stage=summary.stage,
        status=generation_status,
        generated_image_path=f"/api/download/{session_id}",
        generated_image_meta=None,
        download_url=f"/api/download/{session_id}",
    )


@router.get("/api/download/{session_id}")
async def download_image(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
) -> FileResponse:
    download_path = session_service.get_download_path(session_id)
    state = session_service.session_store.get_state(session_id)
    generated_image_meta = state["generated_image_meta"]
    return FileResponse(
        path=download_path,
        media_type=generated_image_meta.media_type if generated_image_meta else "application/octet-stream",
        filename=generated_image_meta.file_name if generated_image_meta else download_path.name,
    )
