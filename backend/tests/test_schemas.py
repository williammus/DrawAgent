import pytest
from pydantic import ValidationError

from app.schemas.artifacts import (
    FinalPromptSpec,
    LogicSpec,
    MapperSpec,
    ReviewSpec,
    StyleSpec,
)
from app.schemas.agents import OrchestratorDecisionSpec
from app.schemas.common import ReviewErrorStage
from app.schemas.events import ReviewFailedEvent


def test_artifact_schemas_accept_valid_payloads() -> None:
    logic = LogicSpec(
        chart_title="Method Overview",
        core_method_summary="Summarize the pipeline.",
        nodes=[{"node_id": "n1", "label": "Encoder"}],
        edges=[{"source": "n1", "target": "n2"}],
    )
    style = StyleSpec(
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
    mapper = MapperSpec(
        narrative_direction="left-to-right",
        section_layout=["input", "backbone", "output"],
        module_positions={"Encoder": "left", "Decoder": "right"},
        grouping_strategy="group by processing stage",
        edge_style_mapping={"data_flow": "solid arrows"},
        visual_hierarchy=["main pipeline", "supporting modules"],
        annotation_strategy="short inline annotations",
        legend_placement="bottom-right",
    )
    review = ReviewSpec(
        passed=False,
        error_stage=ReviewErrorStage.VISUAL_MAPPER,
        reason="Modules overlap visually.",
        fix_suggestion=["Increase spacing between groups."],
    )
    final_prompt = FinalPromptSpec(
        final_prompt_en="A clean scientific pipeline figure.",
        final_prompt_cn="一张简洁的科研流程图。",
        prompt_version="v1",
        generation_notes=["Keep labels short."],
        ready_for_generation=True,
    )

    assert logic.nodes[0].label == "Encoder"
    assert style.primary_palette == ["#003049"]
    assert mapper.module_positions["Encoder"] == "left"
    assert review.error_stage == ReviewErrorStage.VISUAL_MAPPER
    assert final_prompt.ready_for_generation is True


def test_review_schema_rejects_invalid_error_stage() -> None:
    with pytest.raises(ValidationError):
        ReviewSpec(
            passed=False,
            error_stage="bad_stage",
            reason="bad",
        )


def test_review_failed_event_uses_discriminated_payload() -> None:
    event = ReviewFailedEvent(
        session_id="session-1",
        stage="reviewing",
        request_id="req-1",
        message="Review failed.",
        reason="Missing legend placement.",
        error_stage=ReviewErrorStage.STYLE_CONFIGURATOR,
        fix_suggestion=["Add legend placement guidance."],
    )

    assert event.event_type == "review_failed"
    assert event.error_stage == ReviewErrorStage.STYLE_CONFIGURATOR


def test_orchestrator_decision_requires_empty_selected_nodes_when_clarifying() -> None:
    with pytest.raises(ValidationError):
        OrchestratorDecisionSpec(
            intent="clarify",
            requires_clarification=True,
            clarification_question="Please provide the abstract.",
            selected_nodes=["logician"],
            reason="Missing source text.",
            user_message="请补充摘要。",
        )
