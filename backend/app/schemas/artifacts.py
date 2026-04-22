from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import (
    IntentType,
    ReviewPhase,
    StageName,
    WorkflowWarningType,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class TextArtifact(StrictModel):
    tool_name: str
    content: str
    prompt_version: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=utc_now)


class ClarificationAction(StrictModel):
    question: str
    reason: str
    missing_fields: list[str] = Field(default_factory=list)


class WorkflowWarning(StrictModel):
    warning_type: WorkflowWarningType
    message: str
    loop_id: str
    review_phase: ReviewPhase | None = None
    created_at: datetime = Field(default_factory=utc_now)


class GeneratedImageMeta(StrictModel):
    file_name: str
    media_type: str
    size_bytes: int = Field(ge=0)
    relative_path: str
    provider: str = "nano-banana2"
    generated_at: datetime = Field(default_factory=utc_now)


class SessionStateSummary(StrictModel):
    session_id: str
    stage: StageName
    intent: IntentType
    has_source_text: bool
    source_text_locked: bool
    has_logic_artifact: bool
    has_style_artifact: bool
    has_plan_review_artifact: bool
    has_mapper_artifact: bool
    has_final_review_artifact: bool
    has_final_prompt_artifact: bool
    has_bypass_warning: bool
    needs_clarification: bool
    interrupted: bool
    user_confirmed: bool
    error_count: int = Field(ge=0)
    updated_at: datetime
    expires_at: datetime


class CleanupReport(StrictModel):
    ran_at: datetime = Field(default_factory=utc_now)
    removed_sessions: list[str] = Field(default_factory=list)
    removed_directories: list[str] = Field(default_factory=list)
    failed_targets: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
