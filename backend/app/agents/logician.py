from __future__ import annotations

from typing import Any

from app.agents.base import TextArtifactExecutor
from app.graph.state import GraphState
from app.schemas import StageName, TextArtifact


class LogicianExecutor(TextArtifactExecutor):
    agent_name = "logician"
    artifact_slot = "logic_artifact"

    def build_prompt_variables(self, state: GraphState) -> dict[str, Any]:
        source_text = self.require_field(state, "source_text")
        artifacts = state.get("artifacts") or {}
        return {
            "source_text": source_text,
            "source_files": [file_meta.model_dump(mode="json") for file_meta in state["source_files"]],
            "modification_instruction": state["user_feedback"] or "",
            "previous_logic_artifact": (
                artifacts["logic_artifact"].content if artifacts.get("logic_artifact") is not None else ""
            ),
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
            "stage": StageName.LOGIC_READY,
            "last_error": None,
        }
