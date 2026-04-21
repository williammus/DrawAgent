from __future__ import annotations

from typing import Any

from app.agents.helpers import payload_status_summary
from app.graph.state import GraphState
from app.llm import LLMClient
from app.prompts import PromptRegistry, PromptRenderer
from app.schemas import OrchestratorDecisionSpec, StageName
from app.tools import ToolRegistry


class OrchestratorExecutor:
    agent_name = "orchestrator"

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        prompt_registry: PromptRegistry,
        prompt_renderer: PromptRenderer,
        tool_registry: ToolRegistry,
    ) -> None:
        self.llm_client = llm_client
        self.prompt_registry = prompt_registry
        self.prompt_renderer = prompt_renderer
        self.tool_registry = tool_registry

    def run(self, state: GraphState) -> dict[str, Any]:
        template = self.prompt_registry.load_text(self.agent_name)
        prompt_text = self.prompt_renderer.render(template, self.build_prompt_variables(state))
        response = self.llm_client.generate_tool_calls(
            prompt_text,
            tools=self.tool_registry.as_llm_tools(),
        )
        decision = self._build_decision(response, state)
        return {
            "orchestrator_decision": decision,
            "intent": decision.intent,
            "pending_tool_calls": decision.tool_calls,
            "stage": state["stage"] if decision.finish else StageName.PLANNING,
            "last_error": None,
        }

    def build_prompt_variables(self, state: GraphState) -> dict[str, Any]:
        return {
            "current_intent": state["intent"],
            "source_text": state["source_text"] or "",
            "user_feedback": state["user_feedback"] or "",
            "research_context": state["research_context"] or {},
            "payload_status_summary": payload_status_summary(state),
            "last_error": state["last_error"] or "",
        }

    def _build_decision(self, response: dict[str, Any], state: GraphState) -> OrchestratorDecisionSpec:
        tool_calls = response.get("tool_calls", [])
        if tool_calls:
            return OrchestratorDecisionSpec(
                intent=self._resolve_intent(tool_calls),
                tool_calls=tool_calls,
                response_message="Tool calls accepted.",
                finish=False,
                finish_reason=None,
            )

        return OrchestratorDecisionSpec(
            intent=state["intent"],
            tool_calls=[],
            response_message=str(response.get("content") or "Workflow completed."),
            finish=True,
            finish_reason="no_tool_calls_returned",
        )

    def _resolve_intent(self, tool_calls: list[dict[str, Any]]) -> str:
        tool_names = {str(item["tool_name"]) for item in tool_calls}
        if "ask_clarification" in tool_names:
            return "clarify"
        if "logician_tool" in tool_names and "style_configurator_tool" in tool_names:
            return "new_task"
        if "logician_tool" in tool_names:
            return "modify_logic"
        if "style_configurator_tool" in tool_names:
            return "modify_style"
        if "visual_mapper_tool" in tool_names:
            return "modify_layout"
        return "unknown"
