from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import ConfigDict, Field

from app.schemas.artifacts import StrictModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ToolKind(StrEnum):
    BUSINESS = "business"
    CONTROL = "control"


class ToolExecutionStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class ClarificationRequestSpec(StrictModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    reason: str
    expected_fields: list[str] = Field(default_factory=list)


class ToolCallSpec(StrictModel):
    model_config = ConfigDict(extra="forbid")

    call_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResultSpec(StrictModel):
    model_config = ConfigDict(extra="forbid")

    call_id: str
    tool_name: str
    status: ToolExecutionStatus
    output: dict[str, Any] | None = None
    error: str | None = None


class ToolExecutionTraceItem(StrictModel):
    model_config = ConfigDict(extra="forbid")

    call_id: str
    tool_name: str
    status: ToolExecutionStatus
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
    error: str | None = None
