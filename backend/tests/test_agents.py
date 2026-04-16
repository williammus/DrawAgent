import pytest

from app.agents import (
    CriticExecutor,
    LogicianExecutor,
    OrchestratorExecutor,
    StyleConfiguratorExecutor,
    SummaryExecutor,
    VisualMapperExecutor,
)
from app.core.errors import ReviewRejectedError
from app.graph.state import build_initial_graph_state
from app.knowledge import StyleKnowledgeProvider
from app.prompts import PromptRegistry, PromptRenderer
from app.schemas import FinalPromptSpec, LogicSpec, MapperSpec, ReviewSpec, StyleSpec
from app.schemas.common import ReviewErrorStage, StageName


class FakeLLMClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts: list[str] = []

    def generate_json(self, prompt: str, **kwargs):
        self.prompts.append(prompt)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def build_common_kwargs(fake_llm: FakeLLMClient) -> dict[str, object]:
    return {
        "llm_client": fake_llm,
        "prompt_registry": PromptRegistry(),
        "prompt_renderer": PromptRenderer(),
        "max_attempts": 2,
    }


def build_state_with_inputs():
    state = build_initial_graph_state("session-1")
    state["source_text"] = "An encoder processes inputs and a decoder reconstructs outputs."
    state["research_context"] = {"discipline": "computer vision", "target_journal": "CVPR"}
    return state


def build_logic_payload() -> LogicSpec:
    return LogicSpec(
        chart_title="Pipeline",
        core_method_summary="Encoder to decoder.",
        containers=[],
        nodes=[{"node_id": "n1", "label": "Encoder"}],
        edges=[],
    )


def build_style_payload() -> StyleSpec:
    return StyleSpec(
        discipline="computer vision",
        target_journal="CVPR",
        primary_palette=["#003049"],
        secondary_palette=["#EAE2B7"],
        font_family="Source Sans Pro",
        line_style="clean solid lines",
        node_shape_rules={"module": "rounded rectangle"},
        layout_style="left-to-right",
        legend_style="compact legend",
        forbidden_visual_elements=["3D icons"],
        style_keywords=["academic", "clean"],
    )


def build_mapper_payload() -> MapperSpec:
    return MapperSpec(
        narrative_direction="left-to-right",
        section_layout=["input", "output"],
        module_positions={"Encoder": "left"},
        grouping_strategy="by processing stage",
        edge_style_mapping={"data_flow": "solid arrows"},
        visual_hierarchy=["main pipeline"],
        annotation_strategy="inline notes",
        legend_placement="bottom-right",
    )


def build_review_payload(passed: bool = True) -> ReviewSpec:
    return ReviewSpec(
        passed=passed,
        error_stage=None if passed else ReviewErrorStage.VISUAL_MAPPER,
        reason="No conflicts found." if passed else "Modules overlap visually.",
        fix_suggestion=[] if passed else ["Increase spacing."],
    )


def test_orchestrator_executor_returns_structured_decision() -> None:
    state = build_state_with_inputs()
    fake_llm = FakeLLMClient(
        [
            {
                "intent": "new_task",
                "requires_clarification": False,
                "clarification_question": None,
                "selected_nodes": [
                    "logician",
                    "style_configurator",
                    "visual_mapper",
                    "critic",
                    "summary",
                ],
                "reason": "The user provided a new drawing request.",
                "user_message": "开始处理。",
            }
        ]
    )
    executor = OrchestratorExecutor(**build_common_kwargs(fake_llm))

    updates = executor.run(state)

    assert updates["stage"] == StageName.PLANNING
    assert updates["orchestrator_decision"].selected_nodes[0] == "logician"


def test_logician_executor_returns_logic_payload() -> None:
    state = build_state_with_inputs()
    fake_llm = FakeLLMClient(
        [
            {
                "chart_title": "Pipeline",
                "core_method_summary": "Encoder to decoder.",
                "containers": [],
                "nodes": [{"node_id": "n1", "label": "Encoder"}],
                "edges": [],
            }
        ]
    )
    executor = LogicianExecutor(**build_common_kwargs(fake_llm))

    updates = executor.run(state)

    assert updates["stage"] == StageName.LOGIC_READY
    assert updates["payload_logic"].nodes[0].label == "Encoder"


def test_style_configurator_executor_uses_knowledge_pack() -> None:
    state = build_state_with_inputs()
    fake_llm = FakeLLMClient(
        [
            {
                "discipline": "computer vision",
                "target_journal": "CVPR",
                "primary_palette": ["#003049"],
                "secondary_palette": ["#EAE2B7"],
                "font_family": "Source Sans Pro",
                "line_style": "clean solid lines",
                "node_shape_rules": {"module": "rounded rectangle"},
                "layout_style": "left-to-right",
                "legend_style": "compact legend",
                "forbidden_visual_elements": ["3D icons"],
                "style_keywords": ["academic", "clean"],
            }
        ]
    )
    executor = StyleConfiguratorExecutor(
        style_knowledge_provider=StyleKnowledgeProvider(),
        **build_common_kwargs(fake_llm),
    )

    updates = executor.run(state)

    assert updates["stage"] == StageName.STYLE_READY
    assert "computer vision" in fake_llm.prompts[0]


def test_visual_mapper_executor_returns_mapper_payload() -> None:
    state = build_state_with_inputs()
    state["payload_logic"] = build_logic_payload()
    state["payload_style"] = build_style_payload()
    fake_llm = FakeLLMClient(
        [
            {
                "narrative_direction": "left-to-right",
                "section_layout": ["input", "output"],
                "module_positions": {"Encoder": "left"},
                "grouping_strategy": "by processing stage",
                "edge_style_mapping": {"data_flow": "solid arrows"},
                "visual_hierarchy": ["main pipeline"],
                "annotation_strategy": "inline notes",
                "legend_placement": "bottom-right",
            }
        ]
    )
    executor = VisualMapperExecutor(**build_common_kwargs(fake_llm))

    updates = executor.run(state)

    assert updates["stage"] == StageName.MAPPING_READY
    assert updates["payload_mapper"].module_positions["Encoder"] == "left"


def test_critic_executor_raises_review_rejected_for_failed_review() -> None:
    state = build_state_with_inputs()
    state["payload_logic"] = build_logic_payload()
    state["payload_style"] = build_style_payload()
    state["payload_mapper"] = build_mapper_payload()
    fake_llm = FakeLLMClient(
        [
            {
                "passed": False,
                "error_stage": "visual_mapper",
                "reason": "Modules overlap visually.",
                "fix_suggestion": ["Increase spacing."],
            }
        ]
    )
    executor = CriticExecutor(**build_common_kwargs(fake_llm))

    with pytest.raises(ReviewRejectedError) as exc_info:
        executor.run(state)

    assert exc_info.value.details["review"]["error_stage"] == ReviewErrorStage.VISUAL_MAPPER


def test_summary_executor_returns_final_prompt_payload() -> None:
    state = build_state_with_inputs()
    state["payload_logic"] = build_logic_payload()
    state["payload_style"] = build_style_payload()
    state["payload_mapper"] = build_mapper_payload()
    state["payload_review"] = build_review_payload()
    fake_llm = FakeLLMClient(
        [
            {
                "final_prompt_en": "A professional, scientific diagram in the style of a top-tier conference.",
                "final_prompt_cn": "顶会风格科研示意图。",
                "prompt_version": "v1",
                "generation_notes": ["Keep labels short."],
                "ready_for_generation": True,
            }
        ]
    )
    executor = SummaryExecutor(**build_common_kwargs(fake_llm))

    updates = executor.run(state)

    assert isinstance(updates["payload_final"], FinalPromptSpec)
    assert updates["stage"] == StageName.PROMPT_READY
    assert updates["payload_final"].ready_for_generation is True
