from __future__ import annotations

from typing import Any

from app.agents.base import StructuredAgentExecutor
from app.agents.helpers import payload_status_summary
from app.graph.state import GraphState
from app.schemas import OrchestratorDecisionSpec, StageName


class OrchestratorExecutor(StructuredAgentExecutor[OrchestratorDecisionSpec]):
    agent_name = "orchestrator"
    output_model = OrchestratorDecisionSpec

    def build_prompt_variables(self, state: GraphState) -> dict[str, Any]:
        return {
            "current_intent": state["intent"],
            "source_text": state["source_text"] or "",
            "user_feedback": state["user_feedback"] or "",
            "research_context": state["research_context"] or {},
            "payload_status_summary": payload_status_summary(state),
            "last_error": state["last_error"] or "",
        }

    def build_state_updates(
        self,
        state: GraphState,
        artifact: OrchestratorDecisionSpec,
    ) -> dict[str, Any]:
        next_stage = StageName.CLARIFYING if artifact.requires_clarification else StageName.PLANNING
        return {
            "orchestrator_decision": artifact,
            "intent": artifact.intent,
            "needs_clarification": artifact.requires_clarification,
            "stage": next_stage,
            "last_error": None,
        }
