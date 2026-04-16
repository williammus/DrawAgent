from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.artifacts import (
    CleanupReport,
    FinalPromptSpec,
    GeneratedImageMeta,
    LogicSpec,
    MapperSpec,
    ReviewSpec,
    SessionStateSummary,
    StyleSpec,
)
from app.schemas.common import ErrorCode, StageName


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApiErrorDetail(StrictModel):
    code: ErrorCode
    message: str
    details: Any | None = None
    request_id: str


class ApiErrorResponse(StrictModel):
    error: ApiErrorDetail


class SessionInitResponse(StrictModel):
    session_id: str
    summary: SessionStateSummary


class SessionDeleteResponse(StrictModel):
    session_id: str
    deleted: bool
    cleanup: CleanupReport | None = None


class ChatMessageRequest(StrictModel):
    session_id: str
    message: str = Field(min_length=1)
    attachments: list[str] = Field(default_factory=list)


class ChatMessageResponse(StrictModel):
    session_id: str
    stage: StageName
    summary: SessionStateSummary
    response_message: str | None = None


class ArtifactResponse(StrictModel):
    session_id: str
    payload_logic: LogicSpec | None = None
    payload_style: StyleSpec | None = None
    payload_mapper: MapperSpec | None = None
    payload_review: ReviewSpec | None = None
    payload_final: FinalPromptSpec | None = None


class GenerateResponse(StrictModel):
    session_id: str
    stage: StageName
    status: str
    generated_image_path: str | None = None
    generated_image_meta: GeneratedImageMeta | None = None
