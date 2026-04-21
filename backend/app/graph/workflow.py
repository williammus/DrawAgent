from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any, Callable

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.core.errors import DrawAgentError
from app.graph.state import GraphState
from app.graph.stores import WorkflowEventStore
from app.schemas import (
    ClarificationRequestSpec,
    ErrorCode,
    StageName,
    ToolCallSpec,
    ToolExecutionStatus,
    ToolExecutionTraceItem,
    ToolKind,
)
from app.schemas.events import (
    ClarificationRequiredEvent,
    ErrorEvent,
    PromptReadyEvent,
    StageCompletedEvent,
    StageStartedEvent,
)
NodeHandler = Callable[[GraphState, RunnableConfig], dict[str, Any]]


if TYPE_CHECKING:
    from app.agents.factory import AgentRuntime


def build_workflow_app(
    *,
    agent_runtime: AgentRuntime,
    event_store: WorkflowEventStore,
    checkpointer: Any,
    max_error_count: int,
) -> Any:
    builder = StateGraph(GraphState)

    builder.add_node(
        "orchestrator",
        _build_orchestrator_node(agent_runtime, event_store, max_error_count),
    )
    builder.add_node(
        "tool_executor",
        _build_tool_executor_node(agent_runtime, event_store, max_error_count),
    )

    builder.add_edge(START, "orchestrator")
    builder.add_conditional_edges(
        "orchestrator",
        _route_after_orchestrator,
        {"tool_executor": "tool_executor", "end": END},
    )
    builder.add_conditional_edges(
        "tool_executor",
        _route_after_tool_executor,
        {"orchestrator": "orchestrator", "end": END},
    )

    return builder.compile(checkpointer=checkpointer)


def _build_orchestrator_node(
    agent_runtime: "AgentRuntime",
    event_store: WorkflowEventStore,
    max_error_count: int,
) -> NodeHandler:
    def node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
        session_id = _session_id_from_config(config, state)
        request_id = _request_id_from_config(config)
        _emit_stage_started(
            event_store,
            session_id=session_id,
            request_id=request_id,
            stage=StageName.PLANNING,
            message="Orchestrator started.",
        )
        try:
            updates = agent_runtime.orchestrator.run(state)
        except Exception as exc:
            return _build_failure_updates(
                event_store,
                state=state,
                session_id=session_id,
                request_id=request_id,
                stage=StageName.PLANNING,
                message="Orchestrator failed.",
                exception=exc,
                failing_node="orchestrator",
                max_error_count=max_error_count,
            )

        decision = updates["orchestrator_decision"]
        _emit_stage_completed(
            event_store,
            session_id=session_id,
            request_id=request_id,
            stage=StageName.PLANNING,
            message=decision.response_message,
        )
        return {
            **updates,
            "needs_clarification": False,
            "interrupted": False,
            "active_clarification": None,
        }

    return node


def _build_tool_executor_node(
    agent_runtime: "AgentRuntime",
    event_store: WorkflowEventStore,
    max_error_count: int,
) -> NodeHandler:
    def node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
        session_id = _session_id_from_config(config, state)
        request_id = _request_id_from_config(config)
        working_state = deepcopy(state)
        accumulated_trace = list(state["tool_execution_trace"])
        pending_calls = list(state["pending_tool_calls"])
        updates: dict[str, Any] = {"pending_tool_calls": [], "last_error": None}

        for tool_call in pending_calls:
            registration = agent_runtime.tool_registry.get(tool_call.tool_name)
            if registration.kind == ToolKind.CONTROL:
                clarification = ClarificationRequestSpec.model_validate(tool_call.arguments)
                _emit_stage_started(
                    event_store,
                    session_id=session_id,
                    request_id=request_id,
                    stage=StageName.CLARIFYING,
                    message="Clarification requested.",
                )
                event_store.append(
                    session_id,
                    ClarificationRequiredEvent(
                        session_id=session_id,
                        stage=StageName.CLARIFYING,
                        request_id=request_id,
                        message="Clarification is required before the workflow can continue.",
                        clarification_question=clarification.question,
                        reason=clarification.reason,
                        expected_fields=clarification.expected_fields,
                    ),
                )
                answer = interrupt(
                    {
                        "question": clarification.question,
                        "reason": clarification.reason,
                        "expected_fields": clarification.expected_fields,
                    }
                )
                accumulated_trace.append(
                    _build_trace_item(
                        tool_call=tool_call,
                        status=ToolExecutionStatus.INTERRUPTED,
                    )
                )
                _emit_stage_completed(
                    event_store,
                    session_id=session_id,
                    request_id=request_id,
                    stage=StageName.CLARIFYING,
                    message="Clarification received.",
                )
                return {
                    **updates,
                    "tool_execution_trace": accumulated_trace,
                    "active_clarification": None,
                    "needs_clarification": False,
                    "interrupted": False,
                    "user_feedback": str(answer),
                    "stage": StageName.PLANNING,
                }

            _emit_stage_started(
                event_store,
                session_id=session_id,
                request_id=request_id,
                stage=registration.progress_stage or StageName.PLANNING,
                message=f"{tool_call.tool_name} started.",
            )
            outcome = agent_runtime.tool_executor.execute_business_call(working_state, tool_call)
            accumulated_trace.append(outcome.trace_item)
            if outcome.error is not None:
                return _build_failure_updates(
                    event_store,
                    state=working_state,
                    session_id=session_id,
                    request_id=request_id,
                    stage=registration.progress_stage or StageName.FAILED,
                    message=f"{tool_call.tool_name} failed.",
                    exception=outcome.error,
                    failing_node=tool_call.tool_name,
                    max_error_count=max_error_count,
                    extra_updates={"tool_execution_trace": accumulated_trace},
                )

            working_state.update(outcome.state_updates)
            updates.update(outcome.state_updates)
            _emit_stage_completed(
                event_store,
                session_id=session_id,
                request_id=request_id,
                stage=registration.progress_stage or StageName.PLANNING,
                message=f"{tool_call.tool_name} completed.",
            )
            payload_final = outcome.state_updates.get("payload_final")
            if payload_final is not None and payload_final.ready_for_generation:
                event_store.append(
                    session_id,
                    PromptReadyEvent(
                        session_id=session_id,
                        stage=StageName.PROMPT_READY,
                        request_id=request_id,
                        message="Final prompt is ready for generation.",
                        prompt_version=payload_final.prompt_version,
                        ready_for_generation=payload_final.ready_for_generation,
                    ),
                )

        return {
            **updates,
            "tool_execution_trace": accumulated_trace,
            "needs_clarification": False,
            "interrupted": False,
            "active_clarification": None,
        }

    return node


def _route_after_orchestrator(state: GraphState) -> str:
    if state["stage"] == StageName.FAILED:
        return "end"

    decision = state["orchestrator_decision"]
    if decision is None:
        return "end"
    if decision.finish or not state["pending_tool_calls"]:
        return "end"
    return "tool_executor"


def _route_after_tool_executor(state: GraphState) -> str:
    if state["stage"] == StageName.FAILED:
        return "end"
    return "orchestrator"


def _build_failure_updates(
    event_store: WorkflowEventStore,
    *,
    state: GraphState,
    session_id: str,
    request_id: str,
    stage: StageName,
    message: str,
    exception: Exception,
    failing_node: str,
    max_error_count: int,
    extra_updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    error_count = state["error_count"] + 1
    failure_message = str(exception)
    if error_count > max_error_count:
        failure_message = f"Workflow aborted after {error_count} errors. Last error: {exception}"

    _emit_error(
        event_store,
        session_id=session_id,
        request_id=request_id,
        stage=StageName.FAILED,
        message=message,
        error_code=_error_code_for_exception(exception),
        details=_error_details_for_exception(exception, failing_node=failing_node, stage=stage),
    )
    updates = {
        "error_count": error_count,
        "last_error": failure_message,
        "stage": StageName.FAILED,
        "needs_clarification": False,
        "interrupted": False,
        "pending_tool_calls": [],
        "active_clarification": None,
    }
    if extra_updates:
        updates.update(extra_updates)
    return updates


def _build_trace_item(
    *,
    tool_call: ToolCallSpec,
    status: ToolExecutionStatus,
) -> ToolExecutionTraceItem:
    return ToolExecutionTraceItem(
        call_id=tool_call.call_id,
        tool_name=tool_call.tool_name,
        status=status,
    )


def _session_id_from_config(config: RunnableConfig, state: GraphState) -> str:
    configurable = config.get("configurable", {})
    return str(configurable.get("thread_id", state["session_id"]))


def _request_id_from_config(config: RunnableConfig) -> str:
    configurable = config.get("configurable", {})
    return str(configurable.get("request_id", "workflow"))


def _emit_stage_started(
    event_store: WorkflowEventStore,
    *,
    session_id: str,
    request_id: str,
    stage: StageName,
    message: str,
) -> None:
    event_store.append(
        session_id,
        StageStartedEvent(
            session_id=session_id,
            stage=stage,
            request_id=request_id,
            message=message,
        ),
    )


def _emit_stage_completed(
    event_store: WorkflowEventStore,
    *,
    session_id: str,
    request_id: str,
    stage: StageName,
    message: str,
) -> None:
    event_store.append(
        session_id,
        StageCompletedEvent(
            session_id=session_id,
            stage=stage,
            request_id=request_id,
            message=message,
        ),
    )


def _emit_error(
    event_store: WorkflowEventStore,
    *,
    session_id: str,
    request_id: str,
    stage: StageName,
    message: str,
    error_code: ErrorCode,
    details: dict[str, Any] | None,
) -> None:
    event_store.append(
        session_id,
        ErrorEvent(
            session_id=session_id,
            stage=stage,
            request_id=request_id,
            message=message,
            error_code=error_code,
            details=details,
        ),
    )


def _error_code_for_exception(exception: Exception) -> ErrorCode:
    if isinstance(exception, DrawAgentError):
        return exception.error_code
    return ErrorCode.INTERNAL_SERVER_ERROR


def _error_details_for_exception(
    exception: Exception,
    *,
    failing_node: str,
    stage: StageName,
) -> dict[str, Any]:
    base_details: dict[str, Any] = {
        "failing_node": failing_node,
        "failing_stage": stage,
        "exception_type": type(exception).__name__,
        "error": str(exception),
    }
    if isinstance(exception, DrawAgentError):
        if isinstance(exception.details, dict):
            return {**base_details, **exception.details}
        return {**base_details, "details": exception.details}
    return base_details
