from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.graph.state import GraphState


def to_prompt_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def payload_status_summary(state: GraphState) -> dict[str, Any]:
    artifacts = state.get("artifacts") or {}
    return {
        "stage": state["stage"],
        "intent": state["intent"],
        "has_logic": artifacts.get("logic_artifact") is not None,
        "has_style": artifacts.get("style_artifact") is not None,
        "has_plan_review": artifacts.get("plan_review_artifact") is not None,
        "has_mapper": artifacts.get("mapper_artifact") is not None,
        "has_final_review": artifacts.get("final_review_artifact") is not None,
        "has_final": artifacts.get("final_prompt_artifact") is not None,
        "needs_clarification": state["needs_clarification"],
        "parsed_discipline": state.get("parsed_discipline"),
        "parsed_target_venue": state.get("parsed_target_venue"),
        "parsed_target_venue_type": state.get("parsed_target_venue_type"),
    }


def artifact_content(state: GraphState, slot_name: str) -> str:
    artifacts = state.get("artifacts") or {}
    artifact = artifacts.get(slot_name)
    if artifact is None:
        return ""
    return artifact.content
