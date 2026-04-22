from __future__ import annotations

from typing import Any, Annotated, TypedDict, cast

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from app.schemas.artifacts import (
    ClarificationAction,
    FinalPromptSpec,
    GeneratedImageMeta,
    LogicSpec,
    MapperSpec,
    ReviewSpec,
    StoredFileMeta,
    StyleSpec,
    TextArtifact,
    WorkflowWarning,
)
from app.schemas.agents import ControllerToolCall, OrchestratorDecisionSpec, ToolExecutionResult
from app.schemas.common import IntentType, ReviewPhase, StageName


class GraphState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    session_id: str
    stage: StageName
    intent: IntentType
    source_text: str | None
    source_text_locked: bool
    uploaded_files: list[StoredFileMeta]
    source_files: list[StoredFileMeta]
    research_context: dict[str, Any] | None
    user_feedback: str | None
    artifacts: dict[str, TextArtifact | None]
    controller_tool_calls: list[ControllerToolCall]
    last_tool_results: list[ToolExecutionResult]
    pending_clarification: ClarificationAction | None
    loop_id: str
    loop_origin: str | None
    clarification_rounds_in_loop: int
    post_plan_review_rounds_in_loop: int
    post_mapper_review_rounds_in_loop: int
    current_review_phase: ReviewPhase | None
    bypass_warnings: list[WorkflowWarning]

    # Legacy compatibility fields kept until later workflow phases are migrated.
    pending_clarification_question: str | None
    orchestrator_decision: OrchestratorDecisionSpec | None
    payload_logic: LogicSpec | None
    payload_style: StyleSpec | None
    payload_mapper: MapperSpec | None
    payload_review: ReviewSpec | None
    payload_final: FinalPromptSpec | None
    generated_image_path: str | None
    generated_image_meta: GeneratedImageMeta | None
    error_count: int
    last_error: str | None
    needs_clarification: bool
    interrupted: bool
    rollback_target: str | None
    user_confirmed: bool


def build_initial_graph_state(session_id: str) -> GraphState:
    return cast(
        GraphState,
        {
            "messages": [],
            "session_id": session_id,
            "stage": StageName.IDLE,
            "intent": IntentType.UNKNOWN,
            "source_text": None,
            "source_text_locked": False,
            "uploaded_files": [],
            "source_files": [],
            "research_context": None,
            "user_feedback": None,
            "artifacts": {
                "logic_artifact": None,
                "style_artifact": None,
                "plan_review_artifact": None,
                "mapper_artifact": None,
                "final_review_artifact": None,
                "final_prompt_artifact": None,
            },
            "controller_tool_calls": [],
            "last_tool_results": [],
            "pending_clarification": None,
            "loop_id": session_id,
            "loop_origin": None,
            "clarification_rounds_in_loop": 0,
            "post_plan_review_rounds_in_loop": 0,
            "post_mapper_review_rounds_in_loop": 0,
            "current_review_phase": None,
            "bypass_warnings": [],
            "pending_clarification_question": None,
            "orchestrator_decision": None,
            "payload_logic": None,
            "payload_style": None,
            "payload_mapper": None,
            "payload_review": None,
            "payload_final": None,
            "generated_image_path": None,
            "generated_image_meta": None,
            "error_count": 0,
            "last_error": None,
            "needs_clarification": False,
            "interrupted": False,
            "rollback_target": None,
            "user_confirmed": False,
        },
    )
