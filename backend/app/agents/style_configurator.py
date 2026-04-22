from __future__ import annotations

from typing import Any

from app.agents.base import TextArtifactExecutor
from app.graph.state import GraphState
from app.knowledge import StyleKnowledgeProvider
from app.schemas import StageName, TextArtifact


class StyleConfiguratorExecutor(TextArtifactExecutor):
    agent_name = "style_configurator"
    artifact_slot = "style_artifact"

    def __init__(
        self,
        *,
        style_knowledge_provider: StyleKnowledgeProvider,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.style_knowledge_provider = style_knowledge_provider

    def build_prompt_variables(self, state: GraphState) -> dict[str, Any]:
        discipline = str(state.get("parsed_discipline") or "")
        target_venue = str(state.get("parsed_target_venue") or "")
        knowledge = self.style_knowledge_provider.lookup(
            discipline=discipline,
            target_journal=target_venue,
            user_feedback=state["user_feedback"],
        )
        return {
            "source_text": state["source_text"] or "",
            "user_feedback": state["user_feedback"] or "",
            "style_knowledge": knowledge,
            "parsed_discipline": discipline,
            "parsed_target_venue": target_venue,
            "parsed_target_venue_type": state.get("parsed_target_venue_type") or "unknown",
            "parsed_special_requirements": state.get("parsed_special_requirements") or [],
        }

    def build_state_updates(self, state: GraphState, artifact: TextArtifact) -> dict[str, Any]:
        artifacts = dict(state["artifacts"])
        artifacts[self.artifact_slot] = artifact
        artifacts["plan_review_artifact"] = None
        artifacts["mapper_artifact"] = None
        artifacts["final_review_artifact"] = None
        artifacts["final_prompt_artifact"] = None
        return {
            "artifacts": artifacts,
            "stage": StageName.STYLE_READY,
            "last_error": None,
        }
