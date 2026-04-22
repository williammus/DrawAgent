from app.agents import (
    ControllerAgentExecutor,
    CriticExecutor,
    LogicianExecutor,
    StyleConfiguratorExecutor,
    SummaryExecutor,
    ToolDefinition,
    ToolRegistry,
    VisualMapperExecutor,
)
from app.graph.state import build_initial_graph_state
from app.knowledge import StyleKnowledgeProvider
from app.prompts import PromptRegistry, PromptRenderer
from app.schemas import EmptyToolInput, FinalPromptSpec, LogicSpec, MapperSpec, ReviewSpec, StyleSpec
from app.schemas.common import ReviewErrorStage, ReviewPhase, StageName


class FakeLLMClient:
    def __init__(self, *, json_responses=None, tool_responses=None):
        self.json_responses = list(json_responses or [])
        self.tool_responses = list(tool_responses or [])
        self.prompts: list[str] = []

    def generate_json(self, prompt: str, **kwargs):
        self.prompts.append(prompt)
        response = self.json_responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def generate_with_tools(self, prompt: str, **kwargs):
        self.prompts.append(prompt)
        response = self.tool_responses.pop(0)
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


def test_controller_executor_returns_native_tool_calls() -> None:
    state = build_state_with_inputs()
    fake_llm = FakeLLMClient(
        tool_responses=[
            {
                "assistant_text": "",
                "tool_calls": [
                    {"tool_name": "logician_tool", "arguments": {}, "tool_call_id": "call_1"},
                    {"tool_name": "style_configurator_tool", "arguments": {}, "tool_call_id": "call_2"},
                ],
                "finish_reason": "tool_calls",
            }
        ]
    )
    tool_registry = ToolRegistry(
        [
            ToolDefinition(
                tool_name="logician_tool",
                description="Generate logic.",
                input_model=EmptyToolInput,
                tool_kind="business",
                executor_builder=lambda: None,
            ),
            ToolDefinition(
                tool_name="style_configurator_tool",
                description="Generate style.",
                input_model=EmptyToolInput,
                tool_kind="business",
                executor_builder=lambda: None,
            ),
        ]
    )
    executor = ControllerAgentExecutor(
        tool_registry=tool_registry,
        llm_client=fake_llm,
        prompt_registry=PromptRegistry(),
        prompt_renderer=PromptRenderer(),
        prompt_version="v2",
    )

    updates = executor.run(state)

    assert len(updates.tool_calls) == 2
    assert updates.tool_calls[0].tool_name == "logician_tool"


def test_logician_executor_returns_logic_payload() -> None:
    state = build_state_with_inputs()
    fake_llm = FakeLLMClient(
        json_responses=[
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
        json_responses=[
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
        json_responses=[
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


def test_critic_executor_supports_post_plan_without_mapper() -> None:
    state = build_state_with_inputs()
    state["payload_logic"] = build_logic_payload()
    state["payload_style"] = build_style_payload()
    state["current_review_phase"] = ReviewPhase.POST_PLAN
    fake_llm = FakeLLMClient(
        json_responses=[
            {
                "passed": False,
                "error_stage": "style_configurator",
                "reason": "Style needs adjustment.",
                "fix_suggestion": ["Increase contrast."],
            }
        ]
    )
    executor = CriticExecutor(**build_common_kwargs(fake_llm))

    updates = executor.run(state)

    assert updates["payload_review"].passed is False
    assert updates["payload_review"].error_stage == ReviewErrorStage.STYLE_CONFIGURATOR


def test_summary_executor_returns_final_prompt_payload() -> None:
    state = build_state_with_inputs()
    state["payload_logic"] = build_logic_payload()
    state["payload_style"] = build_style_payload()
    state["payload_mapper"] = build_mapper_payload()
    state["payload_review"] = build_review_payload()
    fake_llm = FakeLLMClient(
        json_responses=[
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
