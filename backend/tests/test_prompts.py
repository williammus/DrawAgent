import pytest

from app.core.errors import PromptRenderError
from app.knowledge import StyleKnowledgeProvider
from app.prompts import PromptRegistry, PromptRenderer


def test_prompt_registry_loads_default_prompt_text() -> None:
    registry = PromptRegistry()

    prompt_text = registry.load_text("summary")

    assert "Summary Agent" in prompt_text
    assert registry.available_versions("logician") == ("v2_json",)


def test_prompt_renderer_rejects_missing_variables() -> None:
    renderer = PromptRenderer()

    with pytest.raises(PromptRenderError):
        renderer.render("Hello [[name]] from [[team]]", {"name": "DrawAgent"})


def test_style_knowledge_provider_returns_default_profile_when_no_match() -> None:
    provider = StyleKnowledgeProvider()

    profile = provider.lookup(discipline="unknown field", target_journal="unknown")

    assert profile["profile_name"] == "general_scientific"
    assert profile["discipline"] == "unknown field"
