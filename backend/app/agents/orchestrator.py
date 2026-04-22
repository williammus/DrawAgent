from __future__ import annotations

from typing import Any

from app.agents.base import ControllerExecutor
from app.agents.helpers import payload_status_summary
from app.graph.state import GraphState


class ControllerAgentExecutor(ControllerExecutor):
    agent_name = "orchestrator"

    def __init__(self, *, tool_registry: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.tool_registry = tool_registry

    def build_prompt_variables(self, state: GraphState) -> dict[str, Any]:
        return {
            "current_intent": state["intent"],
            "source_text": state["source_text"] or "",
            "user_feedback": state["user_feedback"] or "",
            "research_context": state["research_context"] or {},
            "payload_status_summary": payload_status_summary(state),
            "last_error": state["last_error"] or "",
            "last_tool_results": [result.model_dump(mode="json") for result in state["last_tool_results"]],
            "bypass_warnings": [warning.model_dump(mode="json") for warning in state["bypass_warnings"]],
            "loop_id": state["loop_id"],
            "clarification_rounds_in_loop": state["clarification_rounds_in_loop"],
            "post_plan_review_rounds_in_loop": state["post_plan_review_rounds_in_loop"],
            "post_mapper_review_rounds_in_loop": state["post_mapper_review_rounds_in_loop"],
        }

    def build_tool_schemas(self) -> list[dict[str, Any]]:
        return self.tool_registry.to_openai_schemas()

    def build_system_prompt(self) -> str:
        return (
            "You are the DrawAgent controller. Use the provided tools to orchestrate work. "
            "When a tool is required, return tool calls instead of JSON plans in assistant text."
        )
