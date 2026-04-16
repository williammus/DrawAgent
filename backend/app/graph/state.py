from __future__ import annotations

from typing import Any, Annotated, TypedDict, cast

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from app.schemas.artifacts import (
    FinalPromptSpec,
    GeneratedImageMeta,
    LogicSpec,
    MapperSpec,
    ReviewSpec,
    StoredFileMeta,
    StyleSpec,
)
from app.schemas.common import IntentType, StageName


class GraphState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    session_id: str
    stage: StageName
    intent: IntentType
    source_text: str | None
    source_files: list[StoredFileMeta]
    research_context: dict[str, Any] | None
    user_feedback: str | None
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
            "source_files": [],
            "research_context": None,
            "user_feedback": None,
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
            "user_confirmed": False,
        },
    )
