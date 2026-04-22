from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from app.schemas.artifacts import StrictModel
from app.schemas.common import ReviewPhase, WorkflowWarningType


class EmptyToolInput(StrictModel):
    pass


class AskClarificationToolInput(StrictModel):
    question: str
    reason: str
    missing_fields: list[str] = Field(default_factory=list)


class CriticToolInput(StrictModel):
    review_phase: ReviewPhase


class ContextParseResult(StrictModel):
    discipline: str | None = None
    target_venue: str | None = None
    target_venue_type: Literal["journal", "conference", "unknown"] | None = None
    special_requirements: list[str] = Field(default_factory=list)
    special_requirements_action: Literal["append", "replace", "unchanged"] = "append"


class ControllerToolCall(StrictModel):
    tool_call_id: str | None = None
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolExecutionResult(StrictModel):
    tool_name: str
    ok: bool
    message: str
    retry_target: str | None = None
    review_phase: ReviewPhase | None = None
    warning_type: WorkflowWarningType | None = None


class ControllerResponse(StrictModel):
    assistant_text: str = ""
    tool_calls: list[ControllerToolCall] = Field(default_factory=list)
    finish_reason: Literal["stop", "tool_calls", "length", "content_filter"] | str | None = None
