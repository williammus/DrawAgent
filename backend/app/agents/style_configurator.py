from __future__ import annotations

from typing import Any

from app.agents.base import StructuredAgentExecutor
from app.graph.state import GraphState
from app.knowledge import StyleKnowledgeProvider
from app.schemas import StageName, StyleSpec


class StyleConfiguratorExecutor(StructuredAgentExecutor[StyleSpec]):
    agent_name = "style_configurator"
    output_model = StyleSpec

    def __init__(
        self,
        *,
        style_knowledge_provider: StyleKnowledgeProvider,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.style_knowledge_provider = style_knowledge_provider

    def build_prompt_variables(self, state: GraphState) -> dict[str, Any]:
        research_context = state["research_context"] or {}
        discipline = str(research_context.get("discipline", "") or "")
        target_journal = str(research_context.get("target_journal", "") or "")
        knowledge = self.style_knowledge_provider.lookup(
            discipline=discipline,
            target_journal=target_journal,
            user_feedback=state["user_feedback"],
        )
        return {
            "source_text": state["source_text"] or "",
            "research_context": research_context,
            "user_feedback": state["user_feedback"] or "",
            "style_knowledge": knowledge,
        }

    def build_state_updates(self, state: GraphState, artifact: StyleSpec) -> dict[str, Any]:
        return {
            "payload_style": artifact,
            "stage": StageName.STYLE_READY,
            "last_error": None,
        }
