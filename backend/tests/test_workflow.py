from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from shutil import rmtree
from types import SimpleNamespace
from uuid import uuid4
from typing import Any

from app.graph import (
    WorkflowCheckpointStore,
    WorkflowEventStore,
    WorkflowRunner,
    build_workflow_app,
)
from app.schemas import (
    ClarificationRequestSpec,
    FinalPromptSpec,
    LogicSpec,
    MapperSpec,
    OrchestratorDecisionSpec,
    ReviewSpec,
    StyleSpec,
    ToolCallSpec,
    ToolExecutionStatus,
    ToolExecutionTraceItem,
)
from app.schemas.common import EventType, IntentType, StageName
from app.storage import CleanupService, SessionStore, TempFileManager
from app.storage.session_store import utc_now
from app.tools import ToolExecutionOutcome, ToolRegistration, ToolRegistry
from app.schemas.tools import ToolKind


TEST_TEMP_ROOT = Path(__file__).resolve().parents[1] / ".test_tmp"
TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)


def make_temp_dir(name: str) -> Path:
    path = TEST_TEMP_ROOT / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


class StubOrchestrator:
    def __init__(self, responses: list[dict[str, Any] | Exception]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class StubBusinessExecutor:
    def __init__(self, updates: dict[str, Any] | Exception) -> None:
        self.updates = updates
        self.calls = 0

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        if isinstance(self.updates, Exception):
            raise self.updates
        return self.updates


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


def build_review_payload(passed: bool = True) -> ReviewSpec:
    return ReviewSpec(
        passed=passed,
        error_stage=None,
        reason="No conflicts found." if passed else "Modules overlap visually.",
        fix_suggestion=[],
    )


def build_final_payload(version: str = "v1") -> FinalPromptSpec:
    return FinalPromptSpec(
        final_prompt_en=f"Final prompt {version}",
        final_prompt_cn=f"最终提示词 {version}",
        prompt_version=version,
        generation_notes=["Keep labels short."],
        ready_for_generation=True,
    )


def decision_updates(
    *,
    intent: IntentType,
    tool_calls: list[ToolCallSpec],
    finish: bool = False,
    response_message: str = "继续执行。",
    stage: StageName = StageName.PLANNING,
) -> dict[str, Any]:
    decision = OrchestratorDecisionSpec(
        intent=intent,
        tool_calls=tool_calls,
        response_message=response_message,
        finish=finish,
        finish_reason="completed" if finish else None,
    )
    return {
        "orchestrator_decision": decision,
        "intent": decision.intent,
        "pending_tool_calls": decision.tool_calls,
        "stage": stage,
        "last_error": None,
    }


def business_call(call_id: str, tool_name: str) -> ToolCallSpec:
    return ToolCallSpec(call_id=call_id, tool_name=tool_name, arguments={})


def clarification_call(call_id: str, question: str) -> ToolCallSpec:
    return ToolCallSpec(
        call_id=call_id,
        tool_name="ask_clarification",
        arguments=ClarificationRequestSpec(
            question=question,
            reason="Missing source details.",
            expected_fields=["source_text"],
        ).model_dump(mode="json"),
    )


def build_runtime(
    *,
    orchestrator: StubOrchestrator,
    tool_registry: ToolRegistry,
    tool_executor: Any,
):
    return SimpleNamespace(
        orchestrator=orchestrator,
        tool_registry=tool_registry,
        tool_executor=tool_executor,
    )


class StubToolExecutor:
    def __init__(self, outcomes: dict[str, list[ToolExecutionOutcome]]) -> None:
        self.outcomes = {key: list(value) for key, value in outcomes.items()}
        self.calls: list[str] = []

    def execute_business_call(self, state: dict[str, Any], tool_call: ToolCallSpec) -> ToolExecutionOutcome:
        self.calls.append(tool_call.tool_name)
        return self.outcomes[tool_call.tool_name].pop(0)


def success_outcome(tool_call: ToolCallSpec, updates: dict[str, Any]) -> ToolExecutionOutcome:
    return ToolExecutionOutcome(
        state_updates=updates,
        trace_item=ToolExecutionTraceItem(
            call_id=tool_call.call_id,
            tool_name=tool_call.tool_name,
            status=ToolExecutionStatus.SUCCEEDED,
        ),
    )


def build_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolRegistration(
            tool_name="ask_clarification",
            kind=ToolKind.CONTROL,
            description="Request clarification.",
            parameters_schema={"type": "object"},
            progress_stage=StageName.CLARIFYING,
        )
    )
    for tool_name, stage in (
        ("logician_tool", StageName.LOGIC_READY),
        ("style_configurator_tool", StageName.STYLE_READY),
        ("visual_mapper_tool", StageName.MAPPING_READY),
        ("critic_tool", StageName.REVIEWING),
        ("summary_tool", StageName.PROMPT_READY),
    ):
        registry.register(
            ToolRegistration(
                tool_name=tool_name,
                kind=ToolKind.BUSINESS,
                description=tool_name,
                parameters_schema={"type": "object"},
                progress_stage=stage,
                executor_factory=lambda: None,
            )
        )
    return registry


def build_workflow_components(runtime: Any, max_error_count: int = 3):
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


def test_workflow_runner_completes_dual_node_new_task_path() -> None:
    registry = build_tool_registry()
    first_calls = [business_call("call_1", "logician_tool"), business_call("call_2", "style_configurator_tool")]
    second_calls = [business_call("call_3", "visual_mapper_tool")]
    third_calls = [business_call("call_4", "critic_tool")]
    fourth_calls = [business_call("call_5", "summary_tool")]
    tool_executor = StubToolExecutor(
        outcomes={
            "logician_tool": [
                success_outcome(first_calls[0], {"payload_logic": build_logic_payload(), "stage": StageName.LOGIC_READY, "last_error": None})
            ],
            "style_configurator_tool": [
                success_outcome(first_calls[1], {"payload_style": build_style_payload(), "stage": StageName.STYLE_READY, "last_error": None})
            ],
            "visual_mapper_tool": [
                success_outcome(second_calls[0], {"payload_mapper": build_mapper_payload(), "stage": StageName.MAPPING_READY, "last_error": None})
            ],
            "critic_tool": [
                success_outcome(third_calls[0], {"payload_review": build_review_payload(), "stage": StageName.REVIEWING, "last_error": None})
            ],
            "summary_tool": [
                success_outcome(fourth_calls[0], {"payload_final": build_final_payload(), "stage": StageName.PROMPT_READY, "last_error": None})
            ],
        }
    )
    runtime = build_runtime(
        orchestrator=StubOrchestrator(
                [
                    decision_updates(intent=IntentType.NEW_TASK, tool_calls=first_calls),
                    decision_updates(intent=IntentType.NEW_TASK, tool_calls=second_calls),
                    decision_updates(intent=IntentType.NEW_TASK, tool_calls=third_calls),
                    decision_updates(intent=IntentType.NEW_TASK, tool_calls=fourth_calls),
                    decision_updates(
                        intent=IntentType.NEW_TASK,
                        tool_calls=[],
                        finish=True,
                        response_message="流程完成",
                        stage=StageName.PROMPT_READY,
                    ),
                ]
            ),
        tool_registry=registry,
        tool_executor=tool_executor,
    )
    session_store, _, event_store, _, runner = build_workflow_components(runtime)
    session_store.create_session("session-new")

    final_state = runner.run("session-new", "req-1", source_text="Encoder decoder pipeline.")

    assert final_state["stage"] == StageName.PROMPT_READY
    assert final_state["payload_final"].ready_for_generation is True
    assert runtime.orchestrator.calls == 5
    assert tool_executor.calls == [
        "logician_tool",
        "style_configurator_tool",
        "visual_mapper_tool",
        "critic_tool",
        "summary_tool",
    ]
    assert [item.tool_name for item in final_state["tool_execution_trace"]] == tool_executor.calls
    event_types = [event.event_type for event in event_store.list_events("session-new")]
    assert EventType.PROMPT_READY in event_types


def test_workflow_runner_interrupts_and_resumes_for_control_tool() -> None:
    registry = build_tool_registry()
    post_resume_calls = [business_call("call_2", "logician_tool")]
    tool_executor = StubToolExecutor(
        outcomes={
            "logician_tool": [
                success_outcome(post_resume_calls[0], {"payload_logic": build_logic_payload(), "stage": StageName.LOGIC_READY, "last_error": None})
            ]
        }
    )
    runtime = build_runtime(
        orchestrator=StubOrchestrator(
            [
                    decision_updates(
                        intent=IntentType.CLARIFY,
                        tool_calls=[clarification_call("call_1", "请补充论文摘要。")],
                    ),
                    decision_updates(intent=IntentType.NEW_TASK, tool_calls=post_resume_calls),
                    decision_updates(
                        intent=IntentType.NEW_TASK,
                        tool_calls=[],
                        finish=True,
                        response_message="流程完成",
                        stage=StageName.LOGIC_READY,
                    ),
                ]
            ),
        tool_registry=registry,
        tool_executor=tool_executor,
    )
    session_store, _, event_store, _, runner = build_workflow_components(runtime)
    session_store.create_session("session-clarify")

    interrupted_state = runner.run("session-clarify", "req-2", source_text="Initial task.")

    assert interrupted_state["stage"] == StageName.CLARIFYING
    assert interrupted_state["needs_clarification"] is True
    assert interrupted_state["interrupted"] is True
    assert interrupted_state["active_clarification"] is not None
    assert EventType.CLARIFICATION_REQUIRED in [
        event.event_type for event in event_store.list_events("session-clarify")
    ]

    resumed_state = runner.resume("session-clarify", "req-3", user_feedback="论文摘要补充如下。")

    assert resumed_state["stage"] == StageName.LOGIC_READY
    assert resumed_state["needs_clarification"] is False
    assert resumed_state["interrupted"] is False
    assert resumed_state["user_feedback"] == "论文摘要补充如下。"
    assert resumed_state["payload_logic"] is not None


def test_workflow_runner_requires_explicit_input_semantics() -> None:
    registry = build_tool_registry()
    runtime = build_runtime(
        orchestrator=StubOrchestrator([]),
        tool_registry=registry,
        tool_executor=StubToolExecutor(outcomes={}),
    )
    session_store, _, _, _, runner = build_workflow_components(runtime)
    session_store.create_session("session-inputs")

    try:
        runner.run("session-inputs", "req-a", source_text="x", user_feedback="y")
    except Exception as exc:
        assert "Exactly one of source_text or user_feedback" in str(exc)
    else:
        raise AssertionError("runner.run should reject ambiguous input semantics")

    try:
        runner.run("session-inputs", "req-b", user_feedback="only feedback")
    except Exception as exc:
        assert "user_feedback requires source_text" in str(exc)
    else:
        raise AssertionError("runner.run should require source_text before feedback")


def test_cleanup_service_clears_workflow_state_for_expired_sessions() -> None:
    registry = build_tool_registry()
    first_calls = [business_call("call_1", "logician_tool")]
    runtime = build_runtime(
        orchestrator=StubOrchestrator(
            [
                decision_updates(intent=IntentType.NEW_TASK, tool_calls=first_calls),
                decision_updates(
                    intent=IntentType.NEW_TASK,
                    tool_calls=[],
                    finish=True,
                    response_message="流程完成",
                    stage=StageName.LOGIC_READY,
                ),
            ]
        ),
        tool_registry=registry,
        tool_executor=StubToolExecutor(
            outcomes={
                "logician_tool": [
                    success_outcome(first_calls[0], {"payload_logic": build_logic_payload(), "stage": StageName.LOGIC_READY, "last_error": None})
                ]
            }
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
        record = session_store.create_session("session-cleanup-workflow")
        temp_file_manager.ensure_session_directories(record.session_id)
        runner.run("session-cleanup-workflow", "req-8", source_text="Encoder decoder pipeline.")
        record.expires_at = utc_now() - timedelta(seconds=1)

        cleanup_service.purge_expired_sessions()

        assert event_store.list_events("session-cleanup-workflow") == []
        snapshot = workflow_app.get_state(checkpoint_store.config("session-cleanup-workflow"))
        assert snapshot.values == {}
    finally:
        rmtree(temp_dir, ignore_errors=True)
