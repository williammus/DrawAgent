import pytest

from app.core.errors import PromptRenderError
from app.knowledge import StyleKnowledgeProvider
from app.prompts import PromptRegistry, PromptRenderer


def test_prompt_registry_loads_default_prompt_text() -> None:
    registry = PromptRegistry()

    prompt_text = registry.load_text("summary")

    assert "Scientific Visualization Architect" in prompt_text
    assert registry.available_versions("logician") == ("v1", "v2")


def test_prompt_renderer_rejects_missing_variables() -> None:
    renderer = PromptRenderer()

    with pytest.raises(PromptRenderError):
        renderer.render("Hello [[name]] from [[team]]", {"name": "DrawAgent"})


def test_style_knowledge_provider_returns_default_profile_when_no_match() -> None:
    provider = StyleKnowledgeProvider()

    profile = provider.lookup(discipline="unknown field", target_journal="unknown")

    assert profile["profile_name"] == "general_scientific"
    assert profile["discipline"] == "unknown field"


def test_default_prompt_versions_all_resolve_to_v2() -> None:
    registry = PromptRegistry()

    for agent_name in (
        "orchestrator",
        "logician",
        "style_configurator",
        "visual_mapper",
        "critic",
        "summary",
    ):
        assert registry.get(agent_name).version == "v2"


def test_v2_prompt_required_variables_match_stage3_boundaries() -> None:
    registry = PromptRegistry()
    renderer = PromptRenderer()

    assert renderer.required_variables(registry.load_text("logician")) == {
        "source_text",
        "source_files",
        "focus_area",
        "modification_instruction",
        "research_context",
    }
    assert renderer.required_variables(registry.load_text("style_configurator")) == {
        "source_text",
        "research_context",
        "user_feedback",
        "style_knowledge",
    }
    assert "source_text" not in renderer.required_variables(registry.load_text("visual_mapper"))
    assert "source_text" not in renderer.required_variables(registry.load_text("critic"))
    assert "source_text" not in renderer.required_variables(registry.load_text("summary"))


def test_all_default_v2_prompts_render_with_expected_variables() -> None:
    registry = PromptRegistry()
    renderer = PromptRenderer()

    rendered = {
        "orchestrator": renderer.render(
            registry.load_text("orchestrator"),
            {
                "current_intent": "new_task",
                "source_text": "full paper content",
                "user_feedback": "",
                "research_context": {"discipline": "computer vision"},
                "payload_status_summary": {"logic": False, "style": False},
                "last_tool_results": [],
                "bypass_warnings": [],
                "clarification_rounds_in_loop": 0,
                "post_plan_review_rounds_in_loop": 0,
                "post_mapper_review_rounds_in_loop": 0,
                "loop_id": "loop-1",
                "last_error": "",
            },
        ),
        "logician": renderer.render(
            registry.load_text("logician"),
            {
                "source_text": "source text",
                "source_files": [],
                "focus_area": "",
                "modification_instruction": "",
                "research_context": {},
            },
        ),
        "style_configurator": renderer.render(
            registry.load_text("style_configurator"),
            {
                "source_text": "source text",
                "research_context": {"discipline": "computer vision"},
                "user_feedback": "",
                "style_knowledge": {"profile_name": "general_scientific"},
            },
        ),
        "visual_mapper": renderer.render(
            registry.load_text("visual_mapper"),
            {
                "payload_logic": {"nodes": []},
                "payload_style": {"primary_palette": []},
                "research_context": {},
                "user_feedback": "",
            },
        ),
        "critic": renderer.render(
            registry.load_text("critic"),
            {
                "review_phase": "post_plan",
                "payload_logic": {"nodes": []},
                "payload_style": {"primary_palette": []},
                "payload_mapper": {},
            },
        ),
        "summary": renderer.render(
            registry.load_text("summary"),
            {
                "payload_logic": {"nodes": []},
                "payload_style": {"primary_palette": []},
                "payload_mapper": {"section_layout": []},
                "payload_review": {"passed": True},
                "bypass_warnings": [],
            },
        ),
    }

    assert "tool calling" in rendered["orchestrator"]
    assert '"chart_title"' in rendered["logician"]
    assert '"discipline"' in rendered["style_configurator"]
    assert '"narrative_direction"' in rendered["visual_mapper"]
    assert '"passed"' in rendered["critic"]
    assert '"final_prompt_en"' in rendered["summary"]
