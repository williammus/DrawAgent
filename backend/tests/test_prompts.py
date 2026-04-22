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


def test_v2_prompt_required_variables_match_stage4_boundaries() -> None:
    registry = PromptRegistry()
    renderer = PromptRenderer()

    assert renderer.required_variables(registry.load_text("logician")) == {
        "source_text",
        "modification_instruction",
        "previous_logic_artifact",
    }
    assert renderer.required_variables(registry.load_text("style_configurator")) == {
        "parsed_discipline",
        "parsed_target_venue",
        "parsed_target_venue_type",
        "parsed_special_requirements",
        "user_feedback",
        "source_text",
        "style_knowledge",
    }
    assert "source_text" not in renderer.required_variables(registry.load_text("critic"))
    assert "subject_type" in renderer.required_variables(registry.load_text("critic"))


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
                "payload_status_summary": {"logic": False, "style": False},
                "parsed_discipline": "computer vision",
                "parsed_target_venue": "CVPR",
                "parsed_target_venue_type": "conference",
                "parsed_special_requirements": ["avoid 3D icons"],
                "logic_artifact": "",
                "style_artifact": "",
                "plan_review_artifact": "",
                "mapper_artifact": "",
                "final_review_artifact": "",
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
                "modification_instruction": "",
                "previous_logic_artifact": "",
            },
        ),
        "style_configurator": renderer.render(
            registry.load_text("style_configurator"),
            {
                "parsed_discipline": "computer vision",
                "parsed_target_venue": "CVPR",
                "parsed_target_venue_type": "conference",
                "parsed_special_requirements": ["avoid clutter"],
                "user_feedback": "",
                "source_text": "source text",
                "style_knowledge": {"profile_name": "general_scientific"},
            },
        ),
        "visual_mapper": renderer.render(
            registry.load_text("visual_mapper"),
            {
                "parsed_discipline": "computer vision",
                "logic_artifact": "logic artifact",
                "style_artifact": "style artifact",
                "user_feedback": "",
            },
        ),
        "critic": renderer.render(
            registry.load_text("critic"),
            {
                "review_phase": "post_plan",
                "subject_type": "logician",
                "pre_data": "source text",
                "artifact_data": "logic artifact",
            },
        ),
        "summary": renderer.render(
            registry.load_text("summary"),
            {
                "logic_artifact": "logic artifact",
                "mapper_artifact": "mapper artifact",
                "style_artifact": "style artifact",
                "final_review_artifact": "审查通过，数据无冲突。",
                "bypass_warnings": [],
            },
        ),
    }

    assert "ask_clarification" in rendered["orchestrator"]
    assert "逻辑节点" in rendered["logician"]
    assert "视觉设计指南" in rendered["style_configurator"]
    assert "视觉元素规格书" in rendered["visual_mapper"]
    assert "前置agent类型" in rendered["critic"]
    assert "A professional, scientific diagram" in rendered["summary"]
