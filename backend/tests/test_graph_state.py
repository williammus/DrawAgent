from langchain_core.messages import HumanMessage

from app.graph.state import build_initial_graph_state
from app.schemas.common import IntentType, StageName


def test_build_initial_graph_state_returns_expected_defaults() -> None:
    state = build_initial_graph_state("session-1")

    assert state["session_id"] == "session-1"
    assert state["stage"] == StageName.IDLE
    assert state["intent"] == IntentType.UNKNOWN
    assert state["messages"] == []
    assert state["uploaded_files"] == []
    assert state["source_files"] == []
    assert state["orchestrator_decision"] is None
    assert state["pending_tool_calls"] == []
    assert state["tool_execution_trace"] == []
    assert state["active_clarification"] is None
    assert state["payload_logic"] is None
    assert state["payload_final"] is None
    assert state["error_count"] == 0
    assert state["needs_clarification"] is False
    assert state["interrupted"] is False


def test_graph_state_accepts_langgraph_compatible_messages() -> None:
    state = build_initial_graph_state("session-2")
    state["messages"].append(HumanMessage(content="draw a figure"))

    assert state["messages"][0].content == "draw a figure"
