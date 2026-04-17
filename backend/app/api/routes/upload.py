from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.api.deps import get_session_service
from app.schemas import UploadDeleteResponse, UploadResponse
from app.services import SessionService


router = APIRouter(prefix="/api/upload", tags=["upload"])


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_files(
    session_id: Annotated[str, Form(...)],
    files: Annotated[list[UploadFile], File(...)],
    session_service: SessionService = Depends(get_session_service),
) -> UploadResponse:
    stored_files = await session_service.store_uploads(session_id, files)
    return UploadResponse(session_id=session_id, files=stored_files)


@router.delete("/{session_id}/{file_id}", response_model=UploadDeleteResponse)
async def delete_uploaded_file(
    session_id: str,
    file_id: str,
    session_service: SessionService = Depends(get_session_service),
) -> UploadDeleteResponse:
    session_service.delete_upload(session_id, file_id)
    return UploadDeleteResponse(session_id=session_id, file_id=file_id, deleted=True)
