from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.graph.state import GraphState


def to_prompt_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def payload_status_summary(state: GraphState) -> dict[str, Any]:
    return {
        "stage": state["stage"],
        "intent": state["intent"],
        "has_logic": state["payload_logic"] is not None,
        "has_style": state["payload_style"] is not None,
        "has_mapper": state["payload_mapper"] is not None,
        "has_review": state["payload_review"] is not None,
        "has_final": state["payload_final"] is not None,
        "needs_clarification": state["needs_clarification"],
        "has_pending_tool_calls": bool(state["pending_tool_calls"]),
        "active_clarification": (
            state["active_clarification"].model_dump(mode="json")
            if state["active_clarification"] is not None
            else None
        ),
    }
