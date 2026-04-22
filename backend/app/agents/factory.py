from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from pydantic import BaseModel

from app.agents.critic import CriticExecutor
from app.agents.logician import LogicianExecutor
from app.agents.orchestrator import ControllerAgentExecutor
from app.agents.style_configurator import StyleConfiguratorExecutor
from app.agents.summary import SummaryExecutor
from app.agents.visual_mapper import VisualMapperExecutor
from app.core.errors import InputValidationError
from app.core.settings import Settings
from app.knowledge import StyleKnowledgeProvider
from app.llm import LLMClient
from app.prompts import PromptRegistry, PromptRenderer
from app.schemas import AskClarificationToolInput, CriticToolInput, EmptyToolInput


ToolKind = Literal["control", "business"]


@dataclass(frozen=True)
class ToolDefinition:
    tool_name: str
    description: str
    input_model: type[BaseModel]
    tool_kind: ToolKind
    executor_builder: Callable[[], Any] | None = None

    def to_openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.tool_name,
                "description": self.description,
                "parameters": self.input_model.model_json_schema(),
            },
        }


class ToolRegistry:
    def __init__(self, definitions: list[ToolDefinition]) -> None:
        self._definitions = {definition.tool_name: definition for definition in definitions}

    def get(self, tool_name: str) -> ToolDefinition:
        definition = self._definitions.get(tool_name)
        if definition is None:
            raise InputValidationError(
                "Unknown tool name.",
                details={"tool_name": tool_name, "available_tools": sorted(self._definitions)},
            )
        return definition

    def to_openai_schemas(self) -> list[dict[str, Any]]:
        return [definition.to_openai_schema() for definition in self._definitions.values()]


class ToolFactory:
    def __init__(self, tool_registry: ToolRegistry) -> None:
        self.tool_registry = tool_registry

    def create_executor(self, tool_name: str) -> Any:
        definition = self.tool_registry.get(tool_name)
        if definition.tool_kind != "business":
            raise InputValidationError(
                "Control tools do not have business executors.",
                details={"tool_name": tool_name},
            )
        if definition.executor_builder is None:
            raise InputValidationError(
                "Tool definition does not provide an executor builder.",
                details={"tool_name": tool_name},
            )
        return definition.executor_builder()


@dataclass(frozen=True)
class AgentRuntime:
    controller: ControllerAgentExecutor
    tool_registry: ToolRegistry
    tool_factory: ToolFactory


def build_agent_runtime(
    settings: Settings,
    *,
    llm_client: LLMClient | None = None,
    prompt_registry: PromptRegistry | None = None,
    prompt_renderer: PromptRenderer | None = None,
    style_knowledge_provider: StyleKnowledgeProvider | None = None,
) -> AgentRuntime:
    shared_llm_client = llm_client or LLMClient.from_settings(settings)
    shared_prompt_registry = prompt_registry or PromptRegistry()
    shared_prompt_renderer = prompt_renderer or PromptRenderer()
    shared_style_provider = style_knowledge_provider or StyleKnowledgeProvider()
    common_kwargs = {
        "llm_client": shared_llm_client,
        "prompt_registry": shared_prompt_registry,
        "prompt_renderer": shared_prompt_renderer,
        "max_attempts": settings.llm_max_retries,
    }

    tool_registry = ToolRegistry(
        [
            ToolDefinition(
                tool_name="ask_clarification",
                description="Request structured clarification when the current context is insufficient.",
                input_model=AskClarificationToolInput,
                tool_kind="control",
            ),
            ToolDefinition(
                tool_name="logician_tool",
                description="Generate or revise the logic structure artifact for the drawing task.",
                input_model=EmptyToolInput,
                tool_kind="business",
                executor_builder=lambda: LogicianExecutor(**common_kwargs),
            ),
            ToolDefinition(
                tool_name="style_configurator_tool",
                description="Generate or revise the style configuration artifact for the drawing task.",
                input_model=EmptyToolInput,
                tool_kind="business",
                executor_builder=lambda: StyleConfiguratorExecutor(
                    style_knowledge_provider=shared_style_provider,
                    **common_kwargs,
                ),
            ),
            ToolDefinition(
                tool_name="critic_tool",
                description="Review the current outputs for the requested review phase.",
                input_model=CriticToolInput,
                tool_kind="business",
                executor_builder=lambda: CriticExecutor(**common_kwargs),
            ),
            ToolDefinition(
                tool_name="visual_mapper_tool",
                description="Generate or revise the visual mapping artifact.",
                input_model=EmptyToolInput,
                tool_kind="business",
                executor_builder=lambda: VisualMapperExecutor(**common_kwargs),
            ),
            ToolDefinition(
                tool_name="summary_tool",
                description="Assemble the final prompt artifact for image generation.",
                input_model=EmptyToolInput,
                tool_kind="business",
                executor_builder=lambda: SummaryExecutor(**common_kwargs),
            ),
        ]
    )
    tool_factory = ToolFactory(tool_registry)
    controller = ControllerAgentExecutor(
        tool_registry=tool_registry,
        llm_client=shared_llm_client,
        prompt_registry=shared_prompt_registry,
        prompt_renderer=shared_prompt_renderer,
    )
    return AgentRuntime(
        controller=controller,
        tool_registry=tool_registry,
        tool_factory=tool_factory,
    )
