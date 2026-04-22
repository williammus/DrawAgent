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
from app.schemas import ContextParseResult, EmptyToolInput, ReviewPhase, TextArtifact
from app.schemas.common import StageName


class FakeLLMClient:
    def __init__(self, *, text_responses=None, json_responses=None, tool_responses=None):
        self.text_responses = list(text_responses or [])
        self.json_responses = list(json_responses or [])
        self.tool_responses = list(tool_responses or [])
        self.prompts: list[str] = []

    def generate_text(self, prompt: str, **kwargs):
        self.prompts.append(prompt)
        response = self.text_responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

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
    }


def build_state_with_inputs():
    state = build_initial_graph_state("session-1")
    state["source_text"] = "An encoder processes inputs and a decoder reconstructs outputs."
    state["parsed_discipline"] = "computer vision"
    state["parsed_target_venue"] = "CVPR"
    state["parsed_target_venue_type"] = "conference"
    state["parsed_special_requirements"] = ["highlight the ablation branch"]
    return state


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

    response = executor.run(state)

    assert len(response.tool_calls) == 2
    assert response.tool_calls[0].tool_name == "logician_tool"


def test_controller_executor_parses_context_metadata() -> None:
    state = build_initial_graph_state("session-ctx")
    fake_llm = FakeLLMClient(
        json_responses=[
            {
                "discipline": "bioinformatics",
                "target_venue": "Nature Methods",
                "target_venue_type": "journal",
                "special_requirements": ["avoid warm colors"],
                "special_requirements_action": "append",
            }
        ]
    )
    executor = ControllerAgentExecutor(
        tool_registry=ToolRegistry([]),
        llm_client=fake_llm,
        prompt_registry=PromptRegistry(),
        prompt_renderer=PromptRenderer(),
    )

    parsed = executor.parse_context(latest_input="Target Nature Methods.", state=state)

    assert isinstance(parsed, ContextParseResult)
    assert parsed.target_venue == "Nature Methods"
    assert parsed.target_venue_type == "journal"


def test_logician_executor_writes_text_artifact() -> None:
    state = build_state_with_inputs()
    fake_llm = FakeLLMClient(
        text_responses=["Title: Pipeline\nSummary: Encoder to decoder.\nNodes: Encoder, Decoder"]
    )
    executor = LogicianExecutor(**build_common_kwargs(fake_llm))

    updates = executor.run(state)

    assert updates["stage"] == StageName.LOGIC_READY
    assert updates["artifacts"]["logic_artifact"].content.startswith("Title: Pipeline")


def test_style_configurator_executor_uses_parsed_context() -> None:
    state = build_state_with_inputs()
    fake_llm = FakeLLMClient(text_responses=["Use a restrained blue-gray palette with grid alignment."])
    executor = StyleConfiguratorExecutor(
        style_knowledge_provider=StyleKnowledgeProvider(),
        **build_common_kwargs(fake_llm),
    )

    updates = executor.run(state)

    assert updates["stage"] == StageName.STYLE_READY
    assert "computer vision" in fake_llm.prompts[0]
    assert updates["artifacts"]["style_artifact"].content.startswith("Use a restrained")


def test_visual_mapper_executor_consumes_text_artifacts() -> None:
    state = build_state_with_inputs()
    state["artifacts"]["logic_artifact"] = TextArtifact(
        tool_name="logician",
        content="Logic artifact content",
        prompt_version="v2",
        metadata={},
    )
    state["artifacts"]["style_artifact"] = TextArtifact(
        tool_name="style_configurator",
        content="Style artifact content",
        prompt_version="v2",
        metadata={},
    )
    fake_llm = FakeLLMClient(text_responses=["Section 1: Encoder block on the left."])
    executor = VisualMapperExecutor(**build_common_kwargs(fake_llm))

    updates = executor.run(state)

    assert updates["stage"] == StageName.MAPPING_READY
    assert "Encoder block" in updates["artifacts"]["mapper_artifact"].content


def test_critic_executor_reviews_subject_and_parses_verdict() -> None:
    state = build_state_with_inputs()
    state["artifacts"]["logic_artifact"] = TextArtifact(
        tool_name="logician",
        content="Logic artifact content",
        prompt_version="v2",
        metadata={},
    )
    fake_llm = FakeLLMClient(text_responses=["审查失败：逻辑中遗漏了关键解码模块。"])
    executor = CriticExecutor(**build_common_kwargs(fake_llm))

    artifact = executor.review_subject(
        state,
        subject_type="logician",
        review_phase=ReviewPhase.POST_PLAN,
    )

    assert artifact.metadata["passed"] is False
    assert artifact.metadata["subject_type"] == "logician"


def test_summary_executor_returns_final_prompt_artifact() -> None:
    state = build_state_with_inputs()
    state["artifacts"]["logic_artifact"] = TextArtifact(
        tool_name="logician",
        content="Logic artifact content",
        prompt_version="v2",
        metadata={},
    )
    state["artifacts"]["style_artifact"] = TextArtifact(
        tool_name="style_configurator",
        content="Style artifact content",
        prompt_version="v2",
        metadata={},
    )
    state["artifacts"]["mapper_artifact"] = TextArtifact(
        tool_name="visual_mapper",
        content="Mapper artifact content",
        prompt_version="v2",
        metadata={},
    )
    state["artifacts"]["final_review_artifact"] = TextArtifact(
        tool_name="critic",
        content="审查通过，数据无冲突。",
        prompt_version="v2",
        metadata={"passed": True},
    )
    fake_llm = FakeLLMClient(
        text_responses=[
            "A professional, scientific diagram in the style of a top-tier conference, with a left-to-right encoder-decoder pipeline."
        ]
    )
    executor = SummaryExecutor(**build_common_kwargs(fake_llm))

    updates = executor.run(state)

    assert updates["stage"] == StageName.PROMPT_READY
    artifact = updates["artifacts"]["final_prompt_artifact"]
    assert artifact.metadata["ready_for_generation"] is True
    assert artifact.content.startswith("A professional, scientific diagram")
