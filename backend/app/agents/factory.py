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


@dataclass(frozen=True)
class AgentRuntime:
    orchestrator: OrchestratorExecutor
    logician: LogicianExecutor
    style_configurator: StyleConfiguratorExecutor
    visual_mapper: VisualMapperExecutor
    critic: CriticExecutor
    summary: SummaryExecutor


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

    return AgentRuntime(
        orchestrator=OrchestratorExecutor(**common_kwargs),
        logician=LogicianExecutor(**common_kwargs),
        style_configurator=StyleConfiguratorExecutor(
            style_knowledge_provider=shared_style_provider,
            **common_kwargs,
        ),
        visual_mapper=VisualMapperExecutor(**common_kwargs),
        critic=CriticExecutor(**common_kwargs),
        summary=SummaryExecutor(**common_kwargs),
    )
