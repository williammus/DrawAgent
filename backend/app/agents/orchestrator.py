from __future__ import annotations

from typing import Any

from app.agents.base import ControllerExecutor
from app.agents.helpers import artifact_content, payload_status_summary
from app.graph.state import GraphState
from app.schemas.agents import ContextParseResult


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
            "payload_status_summary": payload_status_summary(state),
            "parsed_discipline": state.get("parsed_discipline") or "",
            "parsed_target_venue": state.get("parsed_target_venue") or "",
            "parsed_target_venue_type": state.get("parsed_target_venue_type") or "unknown",
            "parsed_special_requirements": state.get("parsed_special_requirements") or [],
            "logic_artifact": artifact_content(state, "logic_artifact"),
            "style_artifact": artifact_content(state, "style_artifact"),
            "plan_review_artifact": artifact_content(state, "plan_review_artifact"),
            "mapper_artifact": artifact_content(state, "mapper_artifact"),
            "final_review_artifact": artifact_content(state, "final_review_artifact"),
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

    def parse_context(self, *, latest_input: str, state: GraphState) -> ContextParseResult:
        existing_requirements = state.get("parsed_special_requirements") or []
        prompt = (
            "你是 DrawAgent 的主控agent。请从用户最新输入中提取领域、目标期刊/会议、期刊/会议类型以及特殊要求。"
            "只返回一个 JSON 对象，字段固定为 discipline, target_venue, target_venue_type, "
            "special_requirements, special_requirements_action。"
            "target_venue_type 只能是 journal、conference 或 unknown。"
            "如果输入中没有提供某字段，请返回 null 或 unknown，不要猜测。"
            "special_requirements_action 只能是 append、replace 或 unchanged。"
            "\n\n当前已知信息："
            f"\n- parsed_discipline: {state.get('parsed_discipline') or 'null'}"
            f"\n- parsed_target_venue: {state.get('parsed_target_venue') or 'null'}"
            f"\n- parsed_target_venue_type: {state.get('parsed_target_venue_type') or 'unknown'}"
            f"\n- parsed_special_requirements: {existing_requirements}"
            f"\n\n最新用户输入：\n{latest_input}"
        )
        payload = self.llm_client.generate_json(prompt)
        return ContextParseResult.model_validate(payload)
