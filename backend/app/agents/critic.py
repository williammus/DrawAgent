from __future__ import annotations

from typing import Any

from app.agents.base import PromptDrivenExecutor
from app.agents.helpers import artifact_content
from app.core.errors import ArtifactValidationError, InputValidationError
from app.graph.state import GraphState
from app.schemas import ReviewPhase, TextArtifact


class CriticExecutor(PromptDrivenExecutor):
    agent_name = "critic"

    def review_subject(
        self,
        state: GraphState,
        *,
        subject_type: str,
        review_phase: ReviewPhase,
    ) -> TextArtifact:
        variables = self.build_prompt_variables(
            state,
            subject_type=subject_type,
            review_phase=review_phase,
        )
        prompt_text, prompt_version = self.render_prompt(variables)
        content = self.generate_text_response(prompt_text).strip()
        if not content:
            raise ArtifactValidationError(
                "critic returned empty text artifact.",
                details={"subject_type": subject_type, "review_phase": review_phase},
            )

        verdict = self.parse_verdict(content)
        return TextArtifact(
            tool_name=self.agent_name,
            content=content,
            prompt_version=prompt_version,
            metadata={
                "passed": verdict == "passed",
                "subject_type": subject_type,
                "review_phase": review_phase,
            },
        )

    def parse_verdict(self, content: str) -> str:
        first_line = next((line.strip() for line in content.splitlines() if line.strip()), "")
        if first_line.startswith("审查通过"):
            return "passed"
        if first_line.startswith("审查失败："):
            return "failed"
        raise ArtifactValidationError(
            "critic output must start with 审查通过 or 审查失败：",
            details={"content_preview": content[:200]},
        )

    def build_prompt_variables(
        self,
        state: GraphState,
        *,
        subject_type: str,
        review_phase: ReviewPhase,
    ) -> dict[str, Any]:
        if subject_type == "logician":
            pre_data = state.get("source_text") or ""
            data = artifact_content(state, "logic_artifact")
        elif subject_type == "style_configurator":
            pre_data = {
                "discipline": state.get("parsed_discipline"),
                "target_venue": state.get("parsed_target_venue"),
                "target_venue_type": state.get("parsed_target_venue_type"),
                "special_requirements": state.get("parsed_special_requirements") or [],
            }
            data = artifact_content(state, "style_artifact")
        elif subject_type == "visual_mapper":
            pre_data = {
                "logic_artifact": artifact_content(state, "logic_artifact"),
                "style_artifact": artifact_content(state, "style_artifact"),
            }
            data = artifact_content(state, "mapper_artifact")
        else:
            raise InputValidationError(
                "Unknown critic subject type.",
                details={"subject_type": subject_type},
            )

        if not data:
            raise InputValidationError(
                "critic requires artifact content for the current subject.",
                details={"subject_type": subject_type, "review_phase": review_phase},
            )

        return {
            "subject_type": subject_type,
            "review_phase": review_phase,
            "pre_data": pre_data,
            "artifact_data": data,
        }
