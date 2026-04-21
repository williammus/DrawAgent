import pytest

from app.core.errors import PromptRenderError
from app.knowledge import StyleKnowledgeProvider
from app.prompts import PromptRegistry, PromptRenderer


def test_prompt_registry_loads_orchestrator_v2_by_default() -> None:
    registry = PromptRegistry()

    prompt_text = registry.load_text("orchestrator")

    assert "原生 tool calling" in prompt_text or "tool calling" in prompt_text
    assert registry.available_versions("orchestrator") == ("v1", "v2")
    assert registry.available_versions("logician") == ("v1",)


def test_prompt_renderer_rejects_missing_variables() -> None:
    renderer = PromptRenderer()

    with pytest.raises(PromptRenderError):
        renderer.render("Hello [[name]] from [[team]]", {"name": "DrawAgent"})


def test_style_knowledge_provider_returns_default_profile_when_no_match() -> None:
    provider = StyleKnowledgeProvider()

    profile = provider.lookup(discipline="unknown field", target_journal="unknown")

    assert profile["profile_name"] == "general_scientific"
    assert profile["discipline"] == "unknown field"
