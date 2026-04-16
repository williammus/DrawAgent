from __future__ import annotations

from typing import Any

from app.agents.base import StructuredAgentExecutor
from app.graph.state import GraphState
from app.schemas import MapperSpec, StageName


class VisualMapperExecutor(StructuredAgentExecutor[MapperSpec]):
    agent_name = "visual_mapper"
    output_model = MapperSpec

    def build_prompt_variables(self, state: GraphState) -> dict[str, Any]:
        payload_logic = self.require_field(state, "payload_logic")
        payload_style = self.require_field(state, "payload_style")
        return {
            "payload_logic": payload_logic.model_dump(mode="json"),
            "payload_style": payload_style.model_dump(mode="json"),
            "research_context": state["research_context"] or {},
            "user_feedback": state["user_feedback"] or "",
        }

    def build_state_updates(self, state: GraphState, artifact: MapperSpec) -> dict[str, Any]:
        return {
            "payload_mapper": artifact,
            "stage": StageName.MAPPING_READY,
            "last_error": None,
        }
