from __future__ import annotations

from pydantic import ConfigDict, model_validator

from app.schemas.artifacts import StrictModel
from app.schemas.common import IntentType
from app.schemas.tools import ToolCallSpec


class OrchestratorDecisionSpec(StrictModel):
    model_config = ConfigDict(extra="forbid")

    intent: IntentType
    tool_calls: list[ToolCallSpec]
    response_message: str
    finish: bool = False
    finish_reason: str | None = None

    @model_validator(mode="after")
    def validate_completion_shape(self) -> "OrchestratorDecisionSpec":
        if self.finish and self.tool_calls:
            raise ValueError("tool_calls must be empty when finish is true.")
        if not self.finish and not self.tool_calls:
            raise ValueError("tool_calls are required when finish is false.")
        if self.finish and not self.finish_reason:
            raise ValueError("finish_reason is required when finish is true.")
        return self
