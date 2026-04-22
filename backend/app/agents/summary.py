from __future__ import annotations

from typing import Any

from app.agents.base import TextArtifactExecutor
from app.agents.helpers import artifact_content
from app.core.errors import InputValidationError
from app.graph.state import GraphState
from app.schemas import StageName, TextArtifact


class SummaryExecutor(TextArtifactExecutor):
    agent_name = "summary"
    artifact_slot = "final_prompt_artifact"

    def build_prompt_variables(self, state: GraphState) -> dict[str, Any]:
        logic_artifact = artifact_content(state, "logic_artifact")
        style_artifact = artifact_content(state, "style_artifact")
        mapper_artifact = artifact_content(state, "mapper_artifact")
        final_review_artifact = artifact_content(state, "final_review_artifact")
        if not logic_artifact or not style_artifact or not mapper_artifact:
            raise InputValidationError(
                "Summary executor requires logic, style, and mapper artifacts before prompt assembly."
            )

        return {
            "logic_artifact": logic_artifact,
            "style_artifact": style_artifact,
            "mapper_artifact": mapper_artifact,
            "final_review_artifact": final_review_artifact,
            "bypass_warnings": [warning.model_dump(mode="json") for warning in state["bypass_warnings"]],
        }

    def build_artifact_metadata(self, state: GraphState, content: str) -> dict[str, Any]:
        return {"ready_for_generation": True}

    def build_state_updates(self, state: GraphState, artifact: TextArtifact) -> dict[str, Any]:
        artifacts = dict(state["artifacts"])
        artifacts[self.artifact_slot] = artifact
        return {
            "artifacts": artifacts,
            "stage": StageName.PROMPT_READY,
            "last_error": None,
        }
