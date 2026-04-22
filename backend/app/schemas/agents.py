from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from app.schemas.artifacts import StrictModel
from app.schemas.common import IntentType, NodeName, ReviewPhase, WorkflowWarningType


class OrchestratorDecisionSpec(StrictModel):
    model_config = ConfigDict(extra="forbid")

    intent: IntentType
    requires_clarification: bool
    clarification_question: str | None = None
    selected_nodes: list[NodeName] = Field(default_factory=list)
    reason: str
    user_message: str

    @model_validator(mode="after")
    def validate_clarification_fields(self) -> "OrchestratorDecisionSpec":
        if self.requires_clarification and not self.clarification_question:
            raise ValueError("clarification_question is required when requires_clarification is true.")

        if self.requires_clarification and self.selected_nodes:
            raise ValueError("selected_nodes must be empty when clarification is required.")

        return self


class EmptyToolInput(StrictModel):
    pass


class AskClarificationToolInput(StrictModel):
    question: str
    reason: str
    missing_fields: list[str] = Field(default_factory=list)


class CriticToolInput(StrictModel):
    review_phase: ReviewPhase


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
