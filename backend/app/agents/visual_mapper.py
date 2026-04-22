from __future__ import annotations

from typing import Any

from app.agents.base import TextArtifactExecutor
from app.agents.helpers import artifact_content
from app.core.errors import InputValidationError
from app.graph.state import GraphState
from app.schemas import StageName, TextArtifact


class VisualMapperExecutor(TextArtifactExecutor):
    agent_name = "visual_mapper"
    artifact_slot = "mapper_artifact"

    def build_prompt_variables(self, state: GraphState) -> dict[str, Any]:
        logic_artifact = artifact_content(state, "logic_artifact")
        style_artifact = artifact_content(state, "style_artifact")
        if not logic_artifact or not style_artifact:
            raise InputValidationError("visual_mapper requires logic_artifact and style_artifact.")
        return {
            "logic_artifact": logic_artifact,
            "style_artifact": style_artifact,
            "user_feedback": state["user_feedback"] or "",
            "parsed_discipline": state.get("parsed_discipline") or "",
        }

    def build_state_updates(self, state: GraphState, artifact: TextArtifact) -> dict[str, Any]:
        artifacts = dict(state["artifacts"])
        artifacts[self.artifact_slot] = artifact
        artifacts["final_review_artifact"] = None
        artifacts["final_prompt_artifact"] = None
        return {
            "artifacts": artifacts,
            "stage": StageName.MAPPING_READY,
            "last_error": None,
        }
