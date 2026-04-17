from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from shutil import rmtree
from uuid import uuid4
from typing import Any

from app.agents import AgentRuntime
from app.graph import (
    WorkflowCheckpointStore,
    WorkflowEventStore,
    WorkflowRunner,
    build_initial_graph_state,
    build_workflow_app,
)
from app.schemas import (
    FinalPromptSpec,
    LogicSpec,
    MapperSpec,
    OrchestratorDecisionSpec,
    ReviewSpec,
    StyleSpec,
)
from app.schemas.common import EventType, IntentType, NodeName, ReviewErrorStage, StageName
from app.storage import CleanupService, SessionStore, TempFileManager
from app.storage.session_store import utc_now


TEST_TEMP_ROOT = Path(__file__).resolve().parents[1] / ".test_tmp"
TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)


def make_temp_dir(name: str) -> Path:
    path = TEST_TEMP_ROOT / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


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


def build_orchestrator_update(
    *,
    intent: IntentType,
    selected_nodes: list[NodeName],
    requires_clarification: bool = False,
    clarification_question: str | None = None,
    user_message: str = "继续执行。",
) -> dict[str, Any]:
    return {
        "orchestrator_decision": OrchestratorDecisionSpec(
            intent=intent,
            requires_clarification=requires_clarification,
            clarification_question=clarification_question,
            selected_nodes=selected_nodes,
            reason="Structured route selected.",
            user_message=user_message,
        ),
        "intent": intent,
        "needs_clarification": requires_clarification,
        "stage": StageName.CLARIFYING if requires_clarification else StageName.PLANNING,
        "last_error": None,
    }


def build_runtime(
    *,
    orchestrator: StubExecutor,
    logician: StubExecutor,
    style_configurator: StubExecutor,
    visual_mapper: StubExecutor,
    critic: StubExecutor,
    summary: StubExecutor,
) -> AgentRuntime:
    return AgentRuntime(
        orchestrator=orchestrator,
        logician=logician,
        style_configurator=style_configurator,
        visual_mapper=visual_mapper,
        critic=critic,
        summary=summary,
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


def test_workflow_runner_completes_new_task_path() -> None:
    runtime = build_runtime(
        orchestrator=StubExecutor(
            "orchestrator",
            [
                build_orchestrator_update(
                    intent=IntentType.NEW_TASK,
                    selected_nodes=[
                        NodeName.LOGICIAN,
                        NodeName.STYLE_CONFIGURATOR,
                        NodeName.VISUAL_MAPPER,
                        NodeName.CRITIC,
                        NodeName.SUMMARY,
                    ],
                )
            ],
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
            [{"payload_review": build_review_payload(), "stage": StageName.REVIEWING, "last_error": None}],
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
    assert runtime.logician.calls == 1
    assert runtime.style_configurator.calls == 1
    assert runtime.visual_mapper.calls == 1
    assert runtime.critic.calls == 1
    assert runtime.summary.calls == 1
    event_types = [event.event_type for event in event_store.list_events("session-new")]
    assert event_types[0] == EventType.STAGE_STARTED
    assert EventType.PROMPT_READY in event_types


def test_workflow_runner_replays_only_logic_branch_for_modify_logic() -> None:
    runtime = build_runtime(
        orchestrator=StubExecutor(
            "orchestrator",
            [
                build_orchestrator_update(
                    intent=IntentType.MODIFY_LOGIC,
                    selected_nodes=[
                        NodeName.LOGICIAN,
                        NodeName.VISUAL_MAPPER,
                        NodeName.CRITIC,
                        NodeName.SUMMARY,
                    ],
                )
            ],
        ),
        logician=StubExecutor(
            "logician",
            [{"payload_logic": build_logic_payload("v2"), "stage": StageName.LOGIC_READY, "last_error": None}],
        ),
        style_configurator=StubExecutor("style_configurator", []),
        visual_mapper=StubExecutor(
            "visual_mapper",
            [{"payload_mapper": build_mapper_payload("v2"), "stage": StageName.MAPPING_READY, "last_error": None}],
        ),
        critic=StubExecutor(
            "critic",
            [{"payload_review": build_review_payload(), "stage": StageName.REVIEWING, "last_error": None}],
        ),
        summary=StubExecutor(
            "summary",
            [{"payload_final": build_final_payload("v2"), "stage": StageName.PROMPT_READY, "last_error": None}],
        ),
    )
    session_store, _, _, _, runner = build_workflow_components(runtime)
    state = build_initial_graph_state("session-modify-logic")
    state["source_text"] = "Original task."
    state["user_feedback"] = "Add an extra module."
    state["payload_logic"] = build_logic_payload("v1")
    state["payload_style"] = build_style_payload("v1")
    state["payload_mapper"] = build_mapper_payload("v1")
    state["payload_review"] = build_review_payload()
    state["payload_final"] = build_final_payload("v1")
    session_store.create_session("session-modify-logic", state)

    final_state = runner.run("session-modify-logic", "req-2")

    assert final_state["payload_logic"].chart_title == "Pipeline v2"
    assert final_state["payload_style"].layout_style == "layout-v1"
    assert final_state["payload_mapper"].narrative_direction == "left-to-right-v2"
    assert runtime.logician.calls == 1
    assert runtime.style_configurator.calls == 0
    assert runtime.visual_mapper.calls == 1
    assert runtime.summary.calls == 1


def test_workflow_runner_interrupts_and_resumes_for_clarification() -> None:
    runtime = build_runtime(
        orchestrator=StubExecutor(
            "orchestrator",
            [
                build_orchestrator_update(
                    intent=IntentType.NEW_TASK,
                    selected_nodes=[
                        NodeName.LOGICIAN,
                        NodeName.STYLE_CONFIGURATOR,
                        NodeName.VISUAL_MAPPER,
                        NodeName.CRITIC,
                        NodeName.SUMMARY,
                    ],
                )
            ],
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
            [{"payload_review": build_review_payload(), "stage": StageName.REVIEWING, "last_error": None}],
        ),
        summary=StubExecutor(
            "summary",
            [{"payload_final": build_final_payload(), "stage": StageName.PROMPT_READY, "last_error": None}],
        ),
    )
    session_store, _, event_store, _, runner = build_workflow_components(runtime)
    session_store.create_session("session-clarify", build_initial_graph_state("session-clarify"))

    interrupted_state = runner.run("session-clarify", "req-3")

    assert interrupted_state["stage"] == StageName.CLARIFYING
    assert interrupted_state["needs_clarification"] is True
    assert interrupted_state["interrupted"] is True
    assert interrupted_state["pending_clarification_question"] is not None
    assert EventType.CLARIFICATION_REQUIRED in [
        event.event_type for event in event_store.list_events("session-clarify")
    ]

    resumed_state = runner.resume("session-clarify", "req-4", "Encoder decoder details.")

    assert resumed_state["stage"] == StageName.PROMPT_READY
    assert resumed_state["needs_clarification"] is False
    assert resumed_state["interrupted"] is False
    assert resumed_state["user_feedback"] == "Encoder decoder details."


def test_workflow_runner_rolls_back_to_visual_mapper_after_failed_review() -> None:
    runtime = build_runtime(
        orchestrator=StubExecutor(
            "orchestrator",
            [
                build_orchestrator_update(
                    intent=IntentType.NEW_TASK,
                    selected_nodes=[
                        NodeName.LOGICIAN,
                        NodeName.STYLE_CONFIGURATOR,
                        NodeName.VISUAL_MAPPER,
                        NodeName.CRITIC,
                        NodeName.SUMMARY,
                    ],
                )
            ],
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
            [
                {"payload_mapper": build_mapper_payload("v1"), "stage": StageName.MAPPING_READY, "last_error": None},
                {"payload_mapper": build_mapper_payload("v2"), "stage": StageName.MAPPING_READY, "last_error": None},
            ],
        ),
        critic=StubExecutor(
            "critic",
            [
                {
                    "payload_review": build_review_payload(False, ReviewErrorStage.VISUAL_MAPPER),
                    "stage": StageName.REVIEWING,
                    "last_error": None,
                },
                {"payload_review": build_review_payload(), "stage": StageName.REVIEWING, "last_error": None},
            ],
        ),
        summary=StubExecutor(
            "summary",
            [{"payload_final": build_final_payload("v2"), "stage": StageName.PROMPT_READY, "last_error": None}],
        ),
    )
    session_store, _, event_store, _, runner = build_workflow_components(runtime)
    state = build_initial_graph_state("session-rollback")
    state["source_text"] = "Encoder decoder pipeline."
    session_store.create_session("session-rollback", state)

    final_state = runner.run("session-rollback", "req-5")

    assert final_state["stage"] == StageName.PROMPT_READY
    assert final_state["error_count"] == 1
    assert final_state["payload_mapper"].module_positions["Encoder"] == "v2"
    assert runtime.visual_mapper.calls == 2
    assert runtime.critic.calls == 2
    assert EventType.REVIEW_FAILED in [
        event.event_type for event in event_store.list_events("session-rollback")
    ]


def test_workflow_runner_fails_for_unknown_review_target() -> None:
    runtime = build_runtime(
        orchestrator=StubExecutor(
            "orchestrator",
            [
                build_orchestrator_update(
                    intent=IntentType.NEW_TASK,
                    selected_nodes=[
                        NodeName.LOGICIAN,
                        NodeName.STYLE_CONFIGURATOR,
                        NodeName.VISUAL_MAPPER,
                        NodeName.CRITIC,
                        NodeName.SUMMARY,
                    ],
                )
            ],
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
            [
                {
                    "payload_review": build_review_payload(False, ReviewErrorStage.UNKNOWN),
                    "stage": StageName.REVIEWING,
                    "last_error": None,
                }
            ],
        ),
        summary=StubExecutor("summary", []),
    )
    session_store, _, event_store, _, runner = build_workflow_components(runtime)
    state = build_initial_graph_state("session-unknown-review")
    state["source_text"] = "Encoder decoder pipeline."
    session_store.create_session("session-unknown-review", state)

    final_state = runner.run("session-unknown-review", "req-6")

    assert final_state["stage"] == StageName.FAILED
    assert runtime.summary.calls == 0
    assert EventType.ERROR in [
        event.event_type for event in event_store.list_events("session-unknown-review")
    ]


def test_workflow_runner_trips_error_fuse_on_first_review_failure() -> None:
    runtime = build_runtime(
        orchestrator=StubExecutor(
            "orchestrator",
            [
                build_orchestrator_update(
                    intent=IntentType.NEW_TASK,
                    selected_nodes=[
                        NodeName.LOGICIAN,
                        NodeName.STYLE_CONFIGURATOR,
                        NodeName.VISUAL_MAPPER,
                        NodeName.CRITIC,
                        NodeName.SUMMARY,
                    ],
                )
            ],
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
            [
                {
                    "payload_review": build_review_payload(False, ReviewErrorStage.VISUAL_MAPPER),
                    "stage": StageName.REVIEWING,
                    "last_error": None,
                }
            ],
        ),
        summary=StubExecutor("summary", []),
    )
    session_store, _, event_store, _, runner = build_workflow_components(runtime, max_error_count=0)
    state = build_initial_graph_state("session-fuse")
    state["source_text"] = "Encoder decoder pipeline."
    session_store.create_session("session-fuse", state)

    final_state = runner.run("session-fuse", "req-7")

    assert final_state["stage"] == StageName.FAILED
    assert final_state["error_count"] == 1
    assert runtime.visual_mapper.calls == 1
    assert runtime.summary.calls == 0
    assert EventType.ERROR in [
        event.event_type for event in event_store.list_events("session-fuse")
    ]


def test_cleanup_service_clears_workflow_state_for_expired_sessions() -> None:
    runtime = build_runtime(
        orchestrator=StubExecutor(
            "orchestrator",
            [
                build_orchestrator_update(
                    intent=IntentType.NEW_TASK,
                    selected_nodes=[
                        NodeName.LOGICIAN,
                        NodeName.STYLE_CONFIGURATOR,
                        NodeName.VISUAL_MAPPER,
                        NodeName.CRITIC,
                        NodeName.SUMMARY,
                    ],
                )
            ],
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
            [{"payload_review": build_review_payload(), "stage": StageName.REVIEWING, "last_error": None}],
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
