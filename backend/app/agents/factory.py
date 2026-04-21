from __future__ import annotations

from dataclasses import dataclass

from app.agents.critic import CriticExecutor
from app.agents.logician import LogicianExecutor
from app.agents.orchestrator import OrchestratorExecutor
from app.agents.style_configurator import StyleConfiguratorExecutor
from app.agents.summary import SummaryExecutor
from app.agents.visual_mapper import VisualMapperExecutor
from app.core.settings import Settings
from app.knowledge import StyleKnowledgeProvider
from app.llm import LLMClient
from app.prompts import PromptRegistry, PromptRenderer
from app.schemas.common import StageName
from app.schemas.tools import ToolKind
from app.tools import ToolExecutor, ToolRegistration, ToolRegistry


@dataclass(frozen=True)
class AgentRuntime:
    orchestrator: OrchestratorExecutor
    tool_registry: ToolRegistry
    tool_executor: ToolExecutor


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

    def common_kwargs() -> dict[str, object]:
        return {
            "llm_client": shared_llm_client,
            "prompt_registry": shared_prompt_registry,
            "prompt_renderer": shared_prompt_renderer,
            "max_attempts": settings.llm_max_retries,
        }

    registry = ToolRegistry()
    registry.register(
        ToolRegistration(
            tool_name="ask_clarification",
            kind=ToolKind.CONTROL,
            description="Request the user to clarify missing or ambiguous task information.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "reason": {"type": "string"},
                    "expected_fields": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["question", "reason"],
                "additionalProperties": False,
            },
            progress_stage=StageName.CLARIFYING,
        )
    )
    registry.register(
        ToolRegistration(
            tool_name="logician_tool",
            kind=ToolKind.BUSINESS,
            description="Extract the scientific diagram logic structure from the current task.",
            parameters_schema=_simple_business_parameters_schema(),
            progress_stage=StageName.LOGIC_READY,
            executor_factory=lambda: LogicianExecutor(**common_kwargs()),
        )
    )
    registry.register(
        ToolRegistration(
            tool_name="style_configurator_tool",
            kind=ToolKind.BUSINESS,
            description="Produce the visual style specification for the current task.",
            parameters_schema=_simple_business_parameters_schema(),
            progress_stage=StageName.STYLE_READY,
            executor_factory=lambda: StyleConfiguratorExecutor(
                style_knowledge_provider=shared_style_provider,
                **common_kwargs(),
            ),
        )
    )
    registry.register(
        ToolRegistration(
            tool_name="visual_mapper_tool",
            kind=ToolKind.BUSINESS,
            description="Map approved logic and style into a visual layout plan.",
            parameters_schema=_simple_business_parameters_schema(),
            progress_stage=StageName.MAPPING_READY,
            executor_factory=lambda: VisualMapperExecutor(**common_kwargs()),
        )
    )
    registry.register(
        ToolRegistration(
            tool_name="critic_tool",
            kind=ToolKind.BUSINESS,
            description="Review the current artifacts for consistency and safety.",
            parameters_schema=_simple_business_parameters_schema(),
            progress_stage=StageName.REVIEWING,
            executor_factory=lambda: CriticExecutor(**common_kwargs()),
        )
    )
    registry.register(
        ToolRegistration(
            tool_name="summary_tool",
            kind=ToolKind.BUSINESS,
            description="Assemble the final bilingual generation prompt after review passes.",
            parameters_schema=_simple_business_parameters_schema(),
            progress_stage=StageName.PROMPT_READY,
            executor_factory=lambda: SummaryExecutor(**common_kwargs()),
        )
    )

    return AgentRuntime(
        orchestrator=OrchestratorExecutor(
            llm_client=shared_llm_client,
            prompt_registry=shared_prompt_registry,
            prompt_renderer=shared_prompt_renderer,
            tool_registry=registry,
        ),
        tool_registry=registry,
        tool_executor=ToolExecutor(registry),
    )


def _simple_business_parameters_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "request_note": {"type": "string"},
        },
        "additionalProperties": False,
    }
