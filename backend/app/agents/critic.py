from __future__ import annotations

from typing import Any

from app.agents.base import StructuredAgentExecutor
from app.graph.state import GraphState
from app.schemas import ReviewSpec, StageName


class CriticExecutor(StructuredAgentExecutor[ReviewSpec]):
    agent_name = "critic"
    output_model = ReviewSpec

    def build_prompt_variables(self, state: GraphState) -> dict[str, Any]:
        payload_logic = self.require_field(state, "payload_logic")
        payload_style = self.require_field(state, "payload_style")
        payload_mapper = self.require_field(state, "payload_mapper")
        return {
            "payload_logic": payload_logic.model_dump(mode="json"),
            "payload_style": payload_style.model_dump(mode="json"),
            "payload_mapper": payload_mapper.model_dump(mode="json"),
        }

    def build_state_updates(self, state: GraphState, artifact: ReviewSpec) -> dict[str, Any]:
        return {
            "payload_review": artifact,
            "stage": StageName.REVIEWING,
            "last_error": None,
        }
