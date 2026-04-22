from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from shutil import rmtree
from uuid import uuid4
from typing import Any

from app.agents.factory import AgentRuntime, ToolDefinition, ToolFactory, ToolRegistry
from app.core.errors import LLMInvocationError
from app.graph import (
    WorkflowCheckpointStore,
    WorkflowEventStore,
    WorkflowRunner,
    build_initial_graph_state,
    build_workflow_app,
)
from app.schemas import (
    AskClarificationToolInput,
    ControllerResponse,
    CriticToolInput,
    EmptyToolInput,
    FinalPromptSpec,
    LogicSpec,
    MapperSpec,
    ReviewSpec,
    StyleSpec,
)
from app.schemas.common import EventType, IntentType, ReviewErrorStage, ReviewPhase, StageName
from app.storage import CleanupService, SessionStore, TempFileManager
from app.storage.session_store import utc_now


TEST_TEMP_ROOT = Path(__file__).resolve().parents[1] / ".test_tmp"
TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)


def make_temp_dir(name: str) -> Path:
    path = TEST_TEMP_ROOT / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


class StubController:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def run(self, state: dict[str, Any]) -> ControllerResponse:
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if callable(response):
            response = response(state, self.calls)
        return ControllerResponse.model_validate(response)


class StubExecutor:
    def __init__(self, agent_name: str, responses: list[Any]) -> None:
        self.agent_name = agent_name
        self.responses = list(responses)
        self.calls = 0

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        response = self.responses.pop(0)
        if callable(response):
            return response(state, self.calls)
        if isinstance(response, Exception):
            raise response
        return response


def build_logic_payload(version: str = "v1") -> LogicSpec:
    return LogicSpec(
        chart_title=f"Pipeline {version}",
        core_method_summary=f"Logic summary {version}",
        containers=[],
        nodes=[{"node_id": version, "label": f"Encoder {version}"}],
        edges=[],
    )


def build_style_payload(version: str = "v1") -> StyleSpec:
    return StyleSpec(
        discipline="computer vision",
        target_journal="CVPR",
        primary_palette=["#003049"],
        secondary_palette=["#EAE2B7"],
        font_family=f"Font {version}",
        line_style="clean solid lines",
        node_shape_rules={"module": "rounded rectangle"},
        layout_style=f"layout-{version}",
        legend_style="compact legend",
        forbidden_visual_elements=["3D icons"],
        style_keywords=["academic", version],
    )


def build_mapper_payload(version: str = "v1") -> MapperSpec:
    return MapperSpec(
        narrative_direction=f"left-to-right-{version}",
        section_layout=["input", "output"],
        module_positions={"Encoder": version},
        grouping_strategy="by processing stage",
        edge_style_mapping={"data_flow": "solid arrows"},
        visual_hierarchy=[f"main pipeline {version}"],
        annotation_strategy="inline notes",
        legend_placement="bottom-right",
    )


def build_review_payload(
    passed: bool = True,
    error_stage: ReviewErrorStage | None = None,
) -> ReviewSpec:
    return ReviewSpec(
        passed=passed,
        error_stage=error_stage,
        reason="No conflicts found." if passed else "Modules overlap visually.",
        fix_suggestion=[] if passed else ["Increase spacing."],
    )


def build_final_payload(version: str = "v1") -> FinalPromptSpec:
    return FinalPromptSpec(
        final_prompt_en=f"Final prompt {version}",
        final_prompt_cn=f"最终提示词 {version}",
        prompt_version=version,
        generation_notes=["Keep labels short."],
        ready_for_generation=True,
    )


def build_tool_call(tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "tool_name": tool_name,
        "arguments": arguments or {},
        "tool_call_id": f"{tool_name}-{uuid4().hex}",
    }


def build_controller_response(*tool_calls: dict[str, Any], assistant_text: str = "") -> dict[str, Any]:
    return {
        "assistant_text": assistant_text,
        "tool_calls": list(tool_calls),
        "finish_reason": "tool_calls" if tool_calls else "stop",
    }


def build_runtime(
    *,
    controller: StubController,
    logician: StubExecutor | None = None,
    style_configurator: StubExecutor | None = None,
    visual_mapper: StubExecutor | None = None,
    critic: StubExecutor | None = None,
    summary: StubExecutor | None = None,
) -> AgentRuntime:
    logician = logician or StubExecutor("logician", [])
    style_configurator = style_configurator or StubExecutor("style_configurator", [])
    visual_mapper = visual_mapper or StubExecutor("visual_mapper", [])
    critic = critic or StubExecutor("critic", [])
    summary = summary or StubExecutor("summary", [])

    tool_registry = ToolRegistry(
        [
            ToolDefinition(
                tool_name="ask_clarification",
                description="Request clarification.",
                input_model=AskClarificationToolInput,
                tool_kind="control",
            ),
            ToolDefinition(
                tool_name="logician_tool",
                description="Run logician.",
                input_model=EmptyToolInput,
                tool_kind="business",
                executor_builder=lambda: logician,
            ),
            ToolDefinition(
                tool_name="style_configurator_tool",
                description="Run style configurator.",
                input_model=EmptyToolInput,
                tool_kind="business",
                executor_builder=lambda: style_configurator,
            ),
            ToolDefinition(
                tool_name="visual_mapper_tool",
                description="Run visual mapper.",
                input_model=EmptyToolInput,
                tool_kind="business",
                executor_builder=lambda: visual_mapper,
            ),
            ToolDefinition(
                tool_name="critic_tool",
                description="Run critic.",
                input_model=CriticToolInput,
                tool_kind="business",
                executor_builder=lambda: critic,
            ),
            ToolDefinition(
                tool_name="summary_tool",
                description="Run summary.",
                input_model=EmptyToolInput,
                tool_kind="business",
                executor_builder=lambda: summary,
            ),
        ]
    )
    return AgentRuntime(
        controller=controller,
        tool_registry=tool_registry,
        tool_factory=ToolFactory(tool_registry),
    )


def build_workflow_components(runtime: AgentRuntime, max_error_count: int = 3):
    session_store = SessionStore(ttl_seconds=30)
    checkpoint_store = WorkflowCheckpointStore()
    event_store = WorkflowEventStore()
    workflow_app = build_workflow_app(
        agent_runtime=runtime,
        event_store=event_store,
        checkpointer=checkpoint_store.saver,
        max_error_count=max_error_count,
    )
    runner = WorkflowRunner(
        workflow_app=workflow_app,
        session_store=session_store,
        checkpoint_store=checkpoint_store,
        event_store=event_store,
    )
    return session_store, checkpoint_store, event_store, workflow_app, runner


def test_workflow_graph_contains_only_controller_and_tool_executor() -> None:
    runtime = build_runtime(controller=StubController([build_controller_response()]))
    _, _, _, workflow_app, _ = build_workflow_components(runtime)

    graph_nodes = set(workflow_app.get_graph().nodes)

    assert "controller" in graph_nodes
    assert "tool_executor" in graph_nodes
    assert "orchestrator" not in graph_nodes
    assert "visual_mapper" not in graph_nodes


def test_workflow_runner_completes_new_task_path_via_tool_calls() -> None:
    runtime = build_runtime(
        controller=StubController(
            [
                build_controller_response(
                    build_tool_call("logician_tool"),
                    build_tool_call("style_configurator_tool"),
                ),
                build_controller_response(
                    build_tool_call("critic_tool", {"review_phase": ReviewPhase.POST_PLAN})
                ),
                build_controller_response(build_tool_call("visual_mapper_tool")),
                build_controller_response(
                    build_tool_call("critic_tool", {"review_phase": ReviewPhase.POST_MAPPER})
                ),
                build_controller_response(build_tool_call("summary_tool")),
                build_controller_response(assistant_text="流程完成"),
            ]
        ),
        logician=StubExecutor(
            "logician",
            [{"payload_logic": build_logic_payload(), "stage": StageName.LOGIC_READY, "last_error": None}],
        ),
        style_configurator=StubExecutor(
            "style_configurator",
            [{"payload_style": build_style_payload(), "stage": StageName.STYLE_READY, "last_error": None}],
        ),
        visual_mapper=StubExecutor(
            "visual_mapper",
            [{"payload_mapper": build_mapper_payload(), "stage": StageName.MAPPING_READY, "last_error": None}],
        ),
        critic=StubExecutor(
            "critic",
            [{"payload_review": build_review_payload(), "stage": StageName.REVIEWING, "last_error": None}] * 2,
        ),
        summary=StubExecutor(
            "summary",
            [{"payload_final": build_final_payload(), "stage": StageName.PROMPT_READY, "last_error": None}],
        ),
    )
    session_store, _, event_store, _, runner = build_workflow_components(runtime)
    state = build_initial_graph_state("session-new")
    state["source_text"] = "Encoder decoder pipeline."
    session_store.create_session("session-new", state)

    final_state = runner.run("session-new", "req-1")

    assert final_state["stage"] == StageName.PROMPT_READY
    assert final_state["payload_final"].ready_for_generation is True
    assert final_state["intent"] == IntentType.NEW_TASK
    assert final_state["controller_tool_calls"] == []
    assert EventType.PROMPT_READY in [event.event_type for event in event_store.list_events("session-new")]


def test_workflow_runner_interrupts_and_resumes_for_clarification() -> None:
    runtime = build_runtime(
        controller=StubController(
            [
                build_controller_response(
                    build_tool_call(
                        "ask_clarification",
                        {
                            "question": "请补充研究方法的关键步骤。",
                            "reason": "missing_context",
                            "missing_fields": ["source_text"],
                        },
                    )
                ),
                build_controller_response(build_tool_call("logician_tool")),
                build_controller_response(),
            ]
        ),
        logician=StubExecutor(
            "logician",
            [{"payload_logic": build_logic_payload(), "stage": StageName.LOGIC_READY, "last_error": None}],
        ),
    )
    session_store, _, event_store, _, runner = build_workflow_components(runtime)
    state = build_initial_graph_state("session-clarify")
    state["source_text"] = "Original task."
    session_store.create_session("session-clarify", state)

    interrupted_state = runner.run("session-clarify", "req-3")

    assert interrupted_state["stage"] == StageName.CLARIFYING
    assert interrupted_state["needs_clarification"] is True
    assert interrupted_state["interrupted"] is True
    assert interrupted_state["pending_clarification"].question == "请补充研究方法的关键步骤。"

    resumed_state = runner.resume("session-clarify", "req-4", "Encoder decoder details.")

    assert resumed_state["stage"] == StageName.LOGIC_READY
    assert resumed_state["needs_clarification"] is False
    assert resumed_state["interrupted"] is False
    assert resumed_state["user_feedback"] == "Encoder decoder details."
    assert EventType.CLARIFICATION_REQUIRED in [
        event.event_type for event in event_store.list_events("session-clarify")
    ]


def test_workflow_runner_tracks_post_plan_and_post_mapper_review_counts_separately() -> None:
    runtime = build_runtime(
        controller=StubController(
            [
                build_controller_response(
                    build_tool_call("logician_tool"),
                    build_tool_call("style_configurator_tool"),
                ),
                build_controller_response(
                    build_tool_call("critic_tool", {"review_phase": ReviewPhase.POST_PLAN})
                ),
                build_controller_response(build_tool_call("style_configurator_tool")),
                build_controller_response(
                    build_tool_call("critic_tool", {"review_phase": ReviewPhase.POST_PLAN})
                ),
                build_controller_response(build_tool_call("visual_mapper_tool")),
                build_controller_response(
                    build_tool_call("critic_tool", {"review_phase": ReviewPhase.POST_MAPPER})
                ),
                build_controller_response(build_tool_call("visual_mapper_tool")),
                build_controller_response(
                    build_tool_call("critic_tool", {"review_phase": ReviewPhase.POST_MAPPER})
                ),
                build_controller_response(build_tool_call("summary_tool")),
                build_controller_response(),
            ]
        ),
        logician=StubExecutor(
            "logician",
            [{"payload_logic": build_logic_payload(), "stage": StageName.LOGIC_READY, "last_error": None}],
        ),
        style_configurator=StubExecutor(
            "style_configurator",
            [
                {"payload_style": build_style_payload("v1"), "stage": StageName.STYLE_READY, "last_error": None},
                {"payload_style": build_style_payload("v2"), "stage": StageName.STYLE_READY, "last_error": None},
            ],
        ),
        visual_mapper=StubExecutor(
            "visual_mapper",
            [
                {"payload_mapper": build_mapper_payload("v1"), "stage": StageName.MAPPING_READY, "last_error": None},
                {"payload_mapper": build_mapper_payload("v2"), "stage": StageName.MAPPING_READY, "last_error": None},
            ],
        ),
        critic=StubExecutor(
            "critic",
            [
                {"payload_review": build_review_payload(False, ReviewErrorStage.STYLE_CONFIGURATOR), "stage": StageName.REVIEWING, "last_error": None},
                {"payload_review": build_review_payload(), "stage": StageName.REVIEWING, "last_error": None},
                {"payload_review": build_review_payload(False, ReviewErrorStage.VISUAL_MAPPER), "stage": StageName.REVIEWING, "last_error": None},
                {"payload_review": build_review_payload(), "stage": StageName.REVIEWING, "last_error": None},
            ],
        ),
        summary=StubExecutor(
            "summary",
            [{"payload_final": build_final_payload(), "stage": StageName.PROMPT_READY, "last_error": None}],
        ),
    )
    session_store, _, _, _, runner = build_workflow_components(runtime)
    state = build_initial_graph_state("session-review-counts")
    state["source_text"] = "Encoder decoder pipeline."
    session_store.create_session("session-review-counts", state)

    final_state = runner.run("session-review-counts", "req-5")

    assert final_state["stage"] == StageName.PROMPT_READY
    assert final_state["post_plan_review_rounds_in_loop"] == 1
    assert final_state["post_mapper_review_rounds_in_loop"] == 1


def test_workflow_runner_bypasses_after_third_post_mapper_review_failure() -> None:
    runtime = build_runtime(
        controller=StubController(
            [
                build_controller_response(build_tool_call("visual_mapper_tool")),
                build_controller_response(
                    build_tool_call("critic_tool", {"review_phase": ReviewPhase.POST_MAPPER})
                ),
                build_controller_response(build_tool_call("visual_mapper_tool")),
                build_controller_response(
                    build_tool_call("critic_tool", {"review_phase": ReviewPhase.POST_MAPPER})
                ),
                build_controller_response(build_tool_call("visual_mapper_tool")),
                build_controller_response(
                    build_tool_call("critic_tool", {"review_phase": ReviewPhase.POST_MAPPER})
                ),
                build_controller_response(build_tool_call("summary_tool")),
                build_controller_response(),
            ]
        ),
        visual_mapper=StubExecutor(
            "visual_mapper",
            [
                {"payload_mapper": build_mapper_payload("v1"), "stage": StageName.MAPPING_READY, "last_error": None},
                {"payload_mapper": build_mapper_payload("v2"), "stage": StageName.MAPPING_READY, "last_error": None},
                {"payload_mapper": build_mapper_payload("v3"), "stage": StageName.MAPPING_READY, "last_error": None},
            ],
        ),
        critic=StubExecutor(
            "critic",
            [
                {"payload_review": build_review_payload(False, ReviewErrorStage.VISUAL_MAPPER), "stage": StageName.REVIEWING, "last_error": None},
                {"payload_review": build_review_payload(False, ReviewErrorStage.VISUAL_MAPPER), "stage": StageName.REVIEWING, "last_error": None},
                {"payload_review": build_review_payload(False, ReviewErrorStage.VISUAL_MAPPER), "stage": StageName.REVIEWING, "last_error": None},
            ],
        ),
        summary=StubExecutor(
            "summary",
            [{"payload_final": build_final_payload("warning"), "stage": StageName.PROMPT_READY, "last_error": None}],
        ),
    )
    session_store, _, event_store, _, runner = build_workflow_components(runtime)
    state = build_initial_graph_state("session-review-warning")
    state["source_text"] = "Encoder decoder pipeline."
    state["payload_logic"] = build_logic_payload("base")
    state["payload_style"] = build_style_payload("base")
    session_store.create_session("session-review-warning", state)

    final_state = runner.run("session-review-warning", "req-6")

    assert final_state["stage"] == StageName.PROMPT_READY
    assert final_state["post_mapper_review_rounds_in_loop"] == 3
    assert final_state["payload_review"].passed is True
    assert final_state["bypass_warnings"][-1].warning_type == "review_limit_reached"
    assert EventType.WORKFLOW_WARNING in [
        event.event_type for event in event_store.list_events("session-review-warning")
    ]


def test_workflow_failure_event_includes_diagnostic_details() -> None:
    runtime = build_runtime(
        controller=StubController(
            [
                LLMInvocationError(
                    "LLM invocation failed after retries.",
                    details={
                        "model": "qwen-plus",
                        "base_url": "https://sg.uiuiapi.com/v1",
                        "error": "401 Unauthorized",
                    },
                )
            ]
        )
    )
    session_store, _, event_store, _, runner = build_workflow_components(runtime)
    state = build_initial_graph_state("session-controller-failed")
    state["source_text"] = "Encoder decoder pipeline."
    session_store.create_session("session-controller-failed", state)

    final_state = runner.run("session-controller-failed", "req-7")

    assert final_state["stage"] == StageName.FAILED
    error_event = [
        event for event in event_store.list_events("session-controller-failed") if event.event_type == EventType.ERROR
    ][0]
    assert error_event.message == "Controller failed."
    assert error_event.details["failing_node"] == "controller"
    assert error_event.details["model"] == "qwen-plus"
    assert error_event.details["base_url"] == "https://sg.uiuiapi.com/v1"
    assert error_event.details["error"] == "401 Unauthorized"


def test_cleanup_service_clears_workflow_state_for_expired_sessions() -> None:
    runtime = build_runtime(
        controller=StubController(
            [
                build_controller_response(build_tool_call("summary_tool")),
                build_controller_response(),
            ]
        ),
        summary=StubExecutor(
            "summary",
            [{"payload_final": build_final_payload(), "stage": StageName.PROMPT_READY, "last_error": None}],
        ),
    )
    temp_dir = make_temp_dir("workflow-cleanup")
    try:
        session_store, checkpoint_store, event_store, workflow_app, runner = build_workflow_components(runtime)
        temp_file_manager = TempFileManager(temp_dir)
        cleanup_service = CleanupService(
            session_store,
            temp_file_manager,
            session_cleanup_hooks=[runner.clear_session],
        )
        state = build_initial_graph_state("session-cleanup-workflow")
        state["source_text"] = "Encoder decoder pipeline."
        record = session_store.create_session("session-cleanup-workflow", state)
        temp_file_manager.ensure_session_directories(record.session_id)
        runner.run("session-cleanup-workflow", "req-8")
        record.expires_at = utc_now() - timedelta(seconds=1)

        cleanup_service.purge_expired_sessions()

        assert event_store.list_events("session-cleanup-workflow") == []
        snapshot = workflow_app.get_state(checkpoint_store.config("session-cleanup-workflow"))
        assert snapshot.values == {}
    finally:
        rmtree(temp_dir, ignore_errors=True)
