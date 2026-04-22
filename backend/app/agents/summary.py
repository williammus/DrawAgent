from __future__ import annotations

from typing import Any

from app.agents.base import StructuredAgentExecutor
from app.core.errors import ReviewRejectedError
from app.graph.state import GraphState
from app.schemas import FinalPromptSpec, StageName


class SummaryExecutor(StructuredAgentExecutor[FinalPromptSpec]):
    agent_name = "summary"
    output_model = FinalPromptSpec

    def build_prompt_variables(self, state: GraphState) -> dict[str, Any]:
        payload_logic = self.require_field(state, "payload_logic")
        payload_style = self.require_field(state, "payload_style")
        payload_mapper = self.require_field(state, "payload_mapper")
        payload_review = self.require_field(state, "payload_review")
        if not payload_review.passed:
            raise ReviewRejectedError(
                "Summary executor requires a passed review before prompt assembly.",
                details={"review": payload_review.model_dump(mode="json")},
            )

        return {
            "payload_logic": payload_logic.model_dump(mode="json"),
            "payload_style": payload_style.model_dump(mode="json"),
            "payload_mapper": payload_mapper.model_dump(mode="json"),
            "payload_review": payload_review.model_dump(mode="json"),
            "bypass_warnings": [warning.model_dump(mode="json") for warning in state["bypass_warnings"]],
        }

    def build_state_updates(self, state: GraphState, artifact: FinalPromptSpec) -> dict[str, Any]:
        return {
            "payload_final": artifact,
            "stage": StageName.PROMPT_READY,
            "last_error": None,
        }
