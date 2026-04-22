from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from shutil import rmtree
from typing import Any
from uuid import uuid4

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
    ContextParseResult,
    ControllerResponse,
    CriticToolInput,
    EmptyToolInput,
    TextArtifact,
)
from app.schemas.common import EventType, IntentType, ReviewPhase, StageName
from app.storage import CleanupService, SessionStore, TempFileManager
from app.storage.session_store import utc_now


TEST_TEMP_ROOT = Path(__file__).resolve().parents[1] / ".test_tmp"
TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)


def make_temp_dir(name: str) -> Path:
    path = TEST_TEMP_ROOT / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


class StubController:
    def __init__(self, responses: list[Any], parsed_contexts: list[Any] | None = None) -> None:
        self.responses = list(responses)
        self.parsed_contexts = list(parsed_contexts or [])
        self.calls = 0

    def run(self, state: dict[str, Any]) -> ControllerResponse:
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if callable(response):
            response = response(state, self.calls)
        return ControllerResponse.model_validate(response)

    def parse_context(self, *, latest_input: str, state: dict[str, Any]) -> ContextParseResult:
        if not self.parsed_contexts:
            return ContextParseResult()
        response = self.parsed_contexts.pop(0)
        if callable(response):
            response = response(latest_input, state)
        return ContextParseResult.model_validate(response)


class StubExecutor:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        response = self.responses.pop(0)
        if callable(response):
            return response(state, self.calls)
        return response


class StubCriticExecutor:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def review_subject(self, state: dict[str, Any], *, subject_type: str, review_phase: ReviewPhase) -> TextArtifact:
        self.calls += 1
        response = self.responses.pop(0)
        if callable(response):
            response = response(state, subject_type, review_phase, self.calls)
        return response


def build_artifact(
    tool_name: str,
    content: str,
    *,
    prompt_version: str = "v2",
    metadata: dict[str, Any] | None = None,
) -> TextArtifact:
    return TextArtifact(
        tool_name=tool_name,
        content=content,
        prompt_version=prompt_version,
        metadata=metadata or {},
    )


def business_update(slot: str, artifact: TextArtifact, stage: StageName):
    def apply(state: dict[str, Any], _call_index: int) -> dict[str, Any]:
        artifacts = dict(state["artifacts"])
        artifacts[slot] = artifact
        if slot in {"logic_artifact", "style_artifact"}:
            artifacts["plan_review_artifact"] = None
            artifacts["mapper_artifact"] = None
            artifacts["final_review_artifact"] = None
            artifacts["final_prompt_artifact"] = None
        elif slot == "mapper_artifact":
            artifacts["final_review_artifact"] = None
            artifacts["final_prompt_artifact"] = None
        return {"artifacts": artifacts, "stage": stage, "last_error": None}

    return apply


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
    critic: StubCriticExecutor | None = None,
    summary: StubExecutor | None = None,
) -> AgentRuntime:
    logician = logician or StubExecutor([])
    style_configurator = style_configurator or StubExecutor([])
    visual_mapper = visual_mapper or StubExecutor([])
    critic = critic or StubCriticExecutor([])
    summary = summary or StubExecutor([])

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


def test_workflow_runner_completes_new_task_path_via_text_artifacts() -> None:
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
            ],
            parsed_contexts=[
                {
                    "discipline": "computer vision",
                    "target_venue": "CVPR",
                    "target_venue_type": "conference",
                    "special_requirements": [],
                    "special_requirements_action": "append",
                }
            ],
        ),
        logician=StubExecutor(
            [
                business_update(
                    "logic_artifact",
                    build_artifact("logician", "Logic artifact content"),
                    StageName.LOGIC_READY,
                )
            ],
        ),
        style_configurator=StubExecutor(
            [
                business_update(
                    "style_artifact",
                    build_artifact("style_configurator", "Style artifact content"),
                    StageName.STYLE_READY,
                )
            ],
        ),
        visual_mapper=StubExecutor(
            [
                business_update(
                    "mapper_artifact",
                    build_artifact("visual_mapper", "Mapper artifact content"),
                    StageName.MAPPING_READY,
                )
            ],
        ),
        critic=StubCriticExecutor(
            [
                build_artifact("critic", "审查通过，数据无冲突。", metadata={"passed": True, "subject_type": "logician"}),
                build_artifact("critic", "审查通过，数据无冲突。", metadata={"passed": True, "subject_type": "style_configurator"}),
                build_artifact("critic", "审查通过，数据无冲突。", metadata={"passed": True, "subject_type": "visual_mapper"}),
            ]
        ),
        summary=StubExecutor(
            [
                business_update(
                    "final_prompt_artifact",
                    build_artifact(
                        "summary",
                        "A professional, scientific diagram in the style of a top-tier conference.",
                        metadata={"ready_for_generation": True},
                    ),
                    StageName.PROMPT_READY,
                )
            ],
        ),
    )
    session_store, _, event_store, _, runner = build_workflow_components(runtime)
    state = build_initial_graph_state("session-new")
    session_store.create_session("session-new", state)

    final_state = runner.run("session-new", "req-1", source_text="Encoder decoder pipeline for CVPR.")

    assert final_state["stage"] == StageName.PROMPT_READY
    assert final_state["artifacts"]["final_prompt_artifact"] is not None
    assert final_state["intent"] == IntentType.NEW_TASK
    assert final_state["parsed_target_venue"] == "CVPR"
    assert EventType.PROMPT_READY in [event.event_type for event in event_store.list_events("session-new")]


def test_workflow_runner_interrupts_when_required_context_missing_then_resumes() -> None:
    runtime = build_runtime(
        controller=StubController(
            [
                build_controller_response(build_tool_call("logician_tool")),
                build_controller_response(),
            ],
            parsed_contexts=[
                {
                    "discipline": None,
                    "target_venue": None,
                    "target_venue_type": "unknown",
                    "special_requirements": [],
                    "special_requirements_action": "append",
                },
                {
                    "discipline": "computer vision",
                    "target_venue": "CVPR",
                    "target_venue_type": "conference",
                    "special_requirements": ["keep it minimalist"],
                    "special_requirements_action": "append",
                },
            ],
        ),
        logician=StubExecutor(
            [
                business_update(
                    "logic_artifact",
                    build_artifact("logician", "Logic artifact content"),
                    StageName.LOGIC_READY,
                )
            ],
        ),
    )
    session_store, _, event_store, _, runner = build_workflow_components(runtime)
    state = build_initial_graph_state("session-clarify")
    session_store.create_session("session-clarify", state)

    interrupted_state = runner.run("session-clarify", "req-3", source_text="Original task without venue.")

    assert interrupted_state["stage"] == StageName.CLARIFYING
    assert interrupted_state["needs_clarification"] is True
    assert interrupted_state["pending_clarification"] is not None

    resumed_state = runner.resume("session-clarify", "req-4", "领域是计算机视觉，目标会议是 CVPR。")

    assert resumed_state["stage"] == StageName.LOGIC_READY
    assert resumed_state["parsed_discipline"] == "computer vision"
    assert resumed_state["parsed_target_venue"] == "CVPR"
    assert EventType.CLARIFICATION_REQUIRED in [
        event.event_type for event in event_store.list_events("session-clarify")
    ]


def test_workflow_runner_tracks_review_counts_by_gate() -> None:
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
                build_controller_response(),
            ],
            parsed_contexts=[
                {
                    "discipline": "computer vision",
                    "target_venue": "CVPR",
                    "target_venue_type": "conference",
                    "special_requirements": [],
                    "special_requirements_action": "append",
                }
            ],
        ),
        logician=StubExecutor(
            [
                business_update(
                    "logic_artifact",
                    build_artifact("logician", "Logic artifact"),
                    StageName.LOGIC_READY,
                )
            ],
        ),
        style_configurator=StubExecutor(
            [
                business_update(
                    "style_artifact",
                    build_artifact("style_configurator", "Style artifact v1"),
                    StageName.STYLE_READY,
                ),
                business_update(
                    "style_artifact",
                    build_artifact("style_configurator", "Style artifact v2"),
                    StageName.STYLE_READY,
                ),
            ],
        ),
        visual_mapper=StubExecutor(
            [
                business_update(
                    "mapper_artifact",
                    build_artifact("visual_mapper", "Mapper artifact v1"),
                    StageName.MAPPING_READY,
                ),
                business_update(
                    "mapper_artifact",
                    build_artifact("visual_mapper", "Mapper artifact v2"),
                    StageName.MAPPING_READY,
                ),
            ],
        ),
        critic=StubCriticExecutor(
            [
                build_artifact("critic", "审查通过，数据无冲突。", metadata={"passed": True, "subject_type": "logician"}),
                build_artifact("critic", "审查失败：整体风格严重不符合计算机视觉学科。", metadata={"passed": False, "subject_type": "style_configurator"}),
                build_artifact("critic", "审查通过，数据无冲突。", metadata={"passed": True, "subject_type": "logician"}),
                build_artifact("critic", "审查通过，数据无冲突。", metadata={"passed": True, "subject_type": "style_configurator"}),
                build_artifact("critic", "审查失败：可视化布局遗漏关键模块。", metadata={"passed": False, "subject_type": "visual_mapper"}),
                build_artifact("critic", "审查通过，数据无冲突。", metadata={"passed": True, "subject_type": "visual_mapper"}),
            ]
        ),
    )
    session_store, _, _, _, runner = build_workflow_components(runtime)
    state = build_initial_graph_state("session-review-counts")
    session_store.create_session("session-review-counts", state)

    final_state = runner.run("session-review-counts", "req-5", source_text="Encoder decoder pipeline.")

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
            ],
            parsed_contexts=[
                {
                    "discipline": "computer vision",
                    "target_venue": "CVPR",
                    "target_venue_type": "conference",
                    "special_requirements": [],
                    "special_requirements_action": "append",
                }
            ],
        ),
        visual_mapper=StubExecutor(
            [
                business_update(
                    "mapper_artifact",
                    build_artifact("visual_mapper", "Mapper artifact v1"),
                    StageName.MAPPING_READY,
                ),
                business_update(
                    "mapper_artifact",
                    build_artifact("visual_mapper", "Mapper artifact v2"),
                    StageName.MAPPING_READY,
                ),
                business_update(
                    "mapper_artifact",
                    build_artifact("visual_mapper", "Mapper artifact v3"),
                    StageName.MAPPING_READY,
                ),
            ],
        ),
        critic=StubCriticExecutor(
            [
                build_artifact("critic", "审查失败：连接关系不合理。", metadata={"passed": False, "subject_type": "visual_mapper"}),
                build_artifact("critic", "审查失败：连接关系不合理。", metadata={"passed": False, "subject_type": "visual_mapper"}),
                build_artifact("critic", "审查失败：连接关系不合理。", metadata={"passed": False, "subject_type": "visual_mapper"}),
            ]
        ),
        summary=StubExecutor(
            [
                business_update(
                    "final_prompt_artifact",
                    build_artifact(
                        "summary",
                        "A professional, scientific diagram in the style of a top-tier conference.",
                        metadata={"ready_for_generation": True},
                    ),
                    StageName.PROMPT_READY,
                )
            ],
        ),
    )
    session_store, _, event_store, _, runner = build_workflow_components(runtime)
    state = build_initial_graph_state("session-review-warning")
    state["parsed_discipline"] = "computer vision"
    state["parsed_target_venue"] = "CVPR"
    state["parsed_target_venue_type"] = "conference"
    state["artifacts"]["logic_artifact"] = build_artifact("logician", "Logic base")
    state["artifacts"]["style_artifact"] = build_artifact("style_configurator", "Style base")
    session_store.create_session("session-review-warning", state)

    final_state = runner.run("session-review-warning", "req-6", user_feedback="Adjust layout only.")

    assert final_state["stage"] == StageName.PROMPT_READY
    assert final_state["post_mapper_review_rounds_in_loop"] == 3
    assert final_state["artifacts"]["final_review_artifact"].metadata["passed"] is True
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
            ],
            parsed_contexts=[
                {
                    "discipline": "computer vision",
                    "target_venue": "CVPR",
                    "target_venue_type": "conference",
                    "special_requirements": [],
                    "special_requirements_action": "append",
                }
            ],
        )
    )
    session_store, _, event_store, _, runner = build_workflow_components(runtime)
    state = build_initial_graph_state("session-controller-failed")
    session_store.create_session("session-controller-failed", state)

    final_state = runner.run("session-controller-failed", "req-7", source_text="Encoder decoder pipeline.")

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
            ],
            parsed_contexts=[
                {
                    "discipline": "computer vision",
                    "target_venue": "CVPR",
                    "target_venue_type": "conference",
                    "special_requirements": [],
                    "special_requirements_action": "append",
                }
            ],
        ),
        summary=StubExecutor(
            [
                business_update(
                    "final_prompt_artifact",
                    build_artifact("summary", "A professional prompt", metadata={"ready_for_generation": True}),
                    StageName.PROMPT_READY,
                )
            ],
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
        state["parsed_discipline"] = "computer vision"
        state["parsed_target_venue"] = "CVPR"
        state["parsed_target_venue_type"] = "conference"
        record = session_store.create_session("session-cleanup-workflow", state)
        temp_file_manager.ensure_session_directories(record.session_id)
        runner.run("session-cleanup-workflow", "req-8", user_feedback="continue")
        record.expires_at = utc_now() - timedelta(seconds=1)

        cleanup_service.purge_expired_sessions()

        assert event_store.list_events("session-cleanup-workflow") == []
        snapshot = workflow_app.get_state(checkpoint_store.config("session-cleanup-workflow"))
        assert snapshot.values == {}
    finally:
        rmtree(temp_dir, ignore_errors=True)
