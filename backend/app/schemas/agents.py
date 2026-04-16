from __future__ import annotations

from pydantic import ConfigDict, Field, model_validator

from app.schemas.artifacts import StrictModel
from app.schemas.common import IntentType, NodeName


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
