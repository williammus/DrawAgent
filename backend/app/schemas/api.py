from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.artifacts import (
    CleanupReport,
    GeneratedImageMeta,
    SessionStateSummary,
    StoredFileMeta,
    TextArtifact,
)
from app.schemas.common import ErrorCode, GenerateStatus, StageName


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


class ChatRunRequest(StrictModel):
    session_id: str
    source_text: str | None = Field(default=None, min_length=1)
    user_feedback: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_run_inputs(self) -> "ChatRunRequest":
        if bool(self.source_text) == bool(self.user_feedback):
            raise ValueError("Exactly one of source_text or user_feedback must be provided.")
        return self


class ChatResumeRequest(StrictModel):
    session_id: str
    user_feedback: str = Field(min_length=1)


class ChatWorkflowResponse(StrictModel):
    session_id: str
    stage: StageName
    summary: SessionStateSummary
    accepted: bool = True
    stream_url: str
    operation: str
    response_message: str | None = None


class UploadResponse(StrictModel):
    session_id: str
    files: list[StoredFileMeta] = Field(default_factory=list)


class UploadDeleteResponse(StrictModel):
    session_id: str
    file_id: str
    deleted: bool


class ArtifactResponse(StrictModel):
    session_id: str
    logic_artifact: TextArtifact | None = None
    style_artifact: TextArtifact | None = None
    plan_review_artifact: TextArtifact | None = None
    mapper_artifact: TextArtifact | None = None
    final_review_artifact: TextArtifact | None = None
    final_prompt_artifact: TextArtifact | None = None


class GenerateResponse(StrictModel):
    session_id: str
    stage: StageName
    status: GenerateStatus
    generated_image_path: str | None = None
    generated_image_meta: GeneratedImageMeta | None = None
    download_url: str | None = None


class SseEventEnvelope(StrictModel):
    event_id: int
    event_type: str
    data: dict[str, Any]
