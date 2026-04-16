from __future__ import annotations

from typing import Any

from app.agents.base import StructuredAgentExecutor
from app.graph.state import GraphState
from app.schemas import LogicSpec, StageName


class LogicianExecutor(StructuredAgentExecutor[LogicSpec]):
    agent_name = "logician"
    output_model = LogicSpec

    def build_prompt_variables(self, state: GraphState) -> dict[str, Any]:
        source_text = self.require_field(state, "source_text")
        research_context = state["research_context"] or {}

        return {
            "source_text": source_text,
            "source_files": [file_meta.model_dump(mode="json") for file_meta in state["source_files"]],
            "focus_area": research_context.get("focus_area", ""),
            "modification_instruction": state["user_feedback"] or "",
            "research_context": research_context,
        }

    def build_state_updates(self, state: GraphState, artifact: LogicSpec) -> dict[str, Any]:
        return {
            "payload_logic": artifact,
            "stage": StageName.LOGIC_READY,
            "last_error": None,
        }
