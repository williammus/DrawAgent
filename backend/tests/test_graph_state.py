from langchain_core.messages import HumanMessage

from app.graph.state import build_initial_graph_state
from app.schemas.common import IntentType, StageName


def test_build_initial_graph_state_returns_expected_defaults() -> None:
    state = build_initial_graph_state("session-1")

    assert state["session_id"] == "session-1"
    assert state["stage"] == StageName.IDLE
    assert state["intent"] == IntentType.UNKNOWN
    assert state["messages"] == []
    assert state["source_text_locked"] is False
    assert state["artifacts"]["logic_artifact"] is None
    assert state["controller_tool_calls"] == []
    assert state["last_tool_results"] == []
    assert state["pending_clarification"] is None
    assert state["loop_id"] == "session-1"
    assert state["loop_origin"] is None
    assert state["clarification_rounds_in_loop"] == 0
    assert state["post_plan_review_rounds_in_loop"] == 0
    assert state["post_mapper_review_rounds_in_loop"] == 0
    assert state["current_review_phase"] is None
    assert state["bypass_warnings"] == []
    assert state["uploaded_files"] == []
    assert state["source_files"] == []
    assert state["pending_clarification_question"] is None
    assert state["orchestrator_decision"] is None
    assert state["payload_logic"] is None
    assert state["payload_final"] is None
    assert state["error_count"] == 0
    assert state["needs_clarification"] is False
    assert state["interrupted"] is False
    assert state["rollback_target"] is None


def test_graph_state_accepts_langgraph_compatible_messages() -> None:
    state = build_initial_graph_state("session-2")
    state["messages"].append(HumanMessage(content="draw a figure"))

    assert state["messages"][0].content == "draw a figure"
