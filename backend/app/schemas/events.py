from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ErrorCode, EventType, ReviewErrorStage, StageName


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BaseEvent(StrictModel):
    event_type: EventType
    session_id: str
    stage: StageName
    timestamp: datetime = Field(default_factory=utc_now)
    request_id: str
    message: str


class StageStartedEvent(BaseEvent):
    event_type: Literal[EventType.STAGE_STARTED] = EventType.STAGE_STARTED


class StageCompletedEvent(BaseEvent):
    event_type: Literal[EventType.STAGE_COMPLETED] = EventType.STAGE_COMPLETED


class ClarificationRequiredEvent(BaseEvent):
    event_type: Literal[EventType.CLARIFICATION_REQUIRED] = EventType.CLARIFICATION_REQUIRED
    clarification_question: str


class ReviewFailedEvent(BaseEvent):
    event_type: Literal[EventType.REVIEW_FAILED] = EventType.REVIEW_FAILED
    reason: str
    error_stage: ReviewErrorStage
    fix_suggestion: list[str] = Field(default_factory=list)


class PromptReadyEvent(BaseEvent):
    event_type: Literal[EventType.PROMPT_READY] = EventType.PROMPT_READY
    prompt_version: str
    ready_for_generation: bool


class ImageGeneratedEvent(BaseEvent):
    event_type: Literal[EventType.IMAGE_GENERATED] = EventType.IMAGE_GENERATED
    image_path: str


class ErrorEvent(BaseEvent):
    event_type: Literal[EventType.ERROR] = EventType.ERROR
    error_code: ErrorCode
    details: dict[str, Any] | None = None


AgentEvent = Annotated[
    StageStartedEvent
    | StageCompletedEvent
    | ClarificationRequiredEvent
    | ReviewFailedEvent
    | PromptReadyEvent
    | ImageGeneratedEvent
    | ErrorEvent,
    Field(discriminator="event_type"),
]
