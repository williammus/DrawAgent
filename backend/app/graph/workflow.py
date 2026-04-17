from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.core.errors import DrawAgentError
from app.graph.state import GraphState
from app.graph.stores import WorkflowEventStore
from app.schemas import ErrorCode, NodeName, ReviewErrorStage, StageName
from app.schemas.events import (
    ClarificationRequiredEvent,
    ErrorEvent,
    PromptReadyEvent,
    ReviewFailedEvent,
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

    builder.add_node("input_guard", _build_input_guard_node())
    builder.add_node(
        "orchestrator",
        _build_orchestrator_node(agent_runtime, event_store, max_error_count),
    )
    builder.add_node("ask_clarification", _build_ask_clarification_node())
    builder.add_node("wait_user", _build_wait_user_node(event_store))
    builder.add_node("parallel_entry", _parallel_entry_node)
    builder.add_node("parallel_join", _parallel_join_node)
    builder.add_node(
        "logician_parallel",
        _build_executor_node(
            agent_runtime.logician,
            event_store,
            StageName.LOGIC_READY,
            max_error_count,
            parallel_mode=True,
        ),
    )
    builder.add_node(
        "style_parallel",
        _build_executor_node(
            agent_runtime.style_configurator,
            event_store,
            StageName.STYLE_READY,
            max_error_count,
            parallel_mode=True,
        ),
    )
    builder.add_node(
        "logician_single",
        _build_executor_node(
            agent_runtime.logician,
            event_store,
            StageName.LOGIC_READY,
            max_error_count,
        ),
    )
    builder.add_node(
        "style_single",
        _build_executor_node(
            agent_runtime.style_configurator,
            event_store,
            StageName.STYLE_READY,
            max_error_count,
        ),
    )
    builder.add_node(
        "visual_mapper",
        _build_executor_node(
            agent_runtime.visual_mapper,
            event_store,
            StageName.MAPPING_READY,
            max_error_count,
        ),
    )
    builder.add_node(
        "critic",
        _build_critic_node(agent_runtime, event_store, max_error_count),
    )
    builder.add_node(
        "summary",
        _build_executor_node(
            agent_runtime.summary,
            event_store,
            StageName.PROMPT_READY,
            max_error_count,
        ),
    )

    builder.add_edge(START, "input_guard")
    builder.add_conditional_edges(
        "input_guard",
        _route_after_input_guard,
        {
            "ask_clarification": "ask_clarification",
            "orchestrator": "orchestrator",
        },
    )
    builder.add_edge("ask_clarification", "wait_user")
    builder.add_edge("wait_user", "orchestrator")
    builder.add_conditional_edges(
        "orchestrator",
        _route_after_orchestrator,
        {
            "ask_clarification": "ask_clarification",
            "parallel_entry": "parallel_entry",
            "logician_single": "logician_single",
            "style_single": "style_single",
            "visual_mapper": "visual_mapper",
            "end": END,
        },
    )
    builder.add_edge("parallel_entry", "logician_parallel")
    builder.add_edge("parallel_entry", "style_parallel")
    builder.add_edge(["logician_parallel", "style_parallel"], "parallel_join")
    builder.add_conditional_edges(
        "logician_single",
        _continue_or_end("visual_mapper"),
        {"visual_mapper": "visual_mapper", "end": END},
    )
    builder.add_conditional_edges(
        "style_single",
        _continue_or_end("visual_mapper"),
        {"visual_mapper": "visual_mapper", "end": END},
    )
    builder.add_conditional_edges(
        "parallel_join",
        _continue_or_end("visual_mapper"),
        {"visual_mapper": "visual_mapper", "end": END},
    )
    builder.add_conditional_edges(
        "visual_mapper",
        _continue_or_end("critic"),
        {"critic": "critic", "end": END},
    )
    builder.add_conditional_edges(
        "critic",
        _route_after_critic,
        {
            "summary": "summary",
            "logician_single": "logician_single",
            "style_single": "style_single",
            "visual_mapper": "visual_mapper",
            "end": END,
        },
    )
    builder.add_conditional_edges(
        "summary",
        _continue_or_end("end"),
        {"end": END},
    )

    return builder.compile(checkpointer=checkpointer)


def _build_input_guard_node() -> NodeHandler:
    def node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
        if state["source_text"] or state["source_files"] or state["user_feedback"]:
            return {"pending_clarification_question": None, "last_error": None}

        return {
            "pending_clarification_question": "请补充论文摘要、方法说明或希望修改的具体内容。",
            "last_error": None,
        }

    return node


def _build_orchestrator_node(
    agent_runtime: AgentRuntime,
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
                max_error_count=max_error_count,
            )

        decision = updates["orchestrator_decision"]
        if not decision.requires_clarification and not decision.selected_nodes:
            updates["pending_clarification_question"] = "请明确说明要新建整张图，还是修改逻辑、风格或排版。"

        updates["interrupted"] = False
        updates["rollback_target"] = None
        _emit_stage_completed(
            event_store,
            session_id=session_id,
            request_id=request_id,
            stage=StageName.PLANNING,
            message=decision.user_message,
        )
        return updates

    return node


def _build_ask_clarification_node() -> NodeHandler:
    def node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
        return {
            "stage": StageName.CLARIFYING,
            "needs_clarification": True,
            "interrupted": True,
            "pending_clarification_question": _resolve_clarification_question(state),
            "last_error": None,
            "rollback_target": None,
        }

    return node


def _build_wait_user_node(event_store: WorkflowEventStore) -> NodeHandler:
    def node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
        session_id = _session_id_from_config(config, state)
        request_id = _request_id_from_config(config)
        question = _resolve_clarification_question(state)
        _emit_stage_started(
            event_store,
            session_id=session_id,
            request_id=request_id,
            stage=StageName.CLARIFYING,
            message="Waiting for user clarification.",
        )
        event_store.append(
            session_id,
            ClarificationRequiredEvent(
                session_id=session_id,
                stage=StageName.CLARIFYING,
                request_id=request_id,
                message="Clarification is required before the workflow can continue.",
                clarification_question=question,
            ),
        )
        answer = interrupt({"question": question})
        _emit_stage_completed(
            event_store,
            session_id=session_id,
            request_id=request_id,
            stage=StageName.CLARIFYING,
            message="Clarification received.",
        )
        return {
            "user_feedback": str(answer),
            "needs_clarification": False,
            "interrupted": False,
            "pending_clarification_question": None,
            "stage": StageName.PLANNING,
            "last_error": None,
        }

    return node


def _parallel_entry_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    return {
        "stage": StageName.PLANNING,
        "last_error": state["last_error"],
    }


def _parallel_join_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    return {
        "stage": state["stage"],
        "last_error": state["last_error"],
    }


def _build_executor_node(
    executor: Any,
    event_store: WorkflowEventStore,
    stage: StageName,
    max_error_count: int,
    parallel_mode: bool = False,
) -> NodeHandler:
    def node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
        session_id = _session_id_from_config(config, state)
        request_id = _request_id_from_config(config)
        _emit_stage_started(
            event_store,
            session_id=session_id,
            request_id=request_id,
            stage=stage,
            message=f"{executor.agent_name} started.",
        )
        try:
            updates = executor.run(state)
        except Exception as exc:
            return _build_failure_updates(
                event_store,
                state=state,
                session_id=session_id,
                request_id=request_id,
                stage=stage,
                message=f"{executor.agent_name} failed.",
                exception=exc,
                max_error_count=max_error_count,
            )

        if parallel_mode:
            for field_name in (
                "stage",
                "last_error",
                "pending_clarification_question",
                "interrupted",
                "rollback_target",
            ):
                updates.pop(field_name, None)
        else:
            updates["pending_clarification_question"] = None
            updates["interrupted"] = False
            if stage != StageName.REVIEWING:
                updates["rollback_target"] = None
        _emit_stage_completed(
            event_store,
            session_id=session_id,
            request_id=request_id,
            stage=stage,
            message=f"{executor.agent_name} completed.",
        )
        payload_final = updates.get("payload_final")
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
        return updates

    return node


def _build_critic_node(
    agent_runtime: AgentRuntime,
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
            stage=StageName.REVIEWING,
            message="Critic started.",
        )
        try:
            updates = agent_runtime.critic.run(state)
        except Exception as exc:
            return _build_failure_updates(
                event_store,
                state=state,
                session_id=session_id,
                request_id=request_id,
                stage=StageName.REVIEWING,
                message="Critic failed.",
                exception=exc,
                max_error_count=max_error_count,
            )

        review = updates["payload_review"]
        if review.passed:
            updates["rollback_target"] = None
            _emit_stage_completed(
                event_store,
                session_id=session_id,
                request_id=request_id,
                stage=StageName.REVIEWING,
                message="Critic passed.",
            )
            return updates

        error_count = state["error_count"] + 1
        rollback_target = review.error_stage.value if review.error_stage is not None else None
        event_store.append(
            session_id,
            ReviewFailedEvent(
                session_id=session_id,
                stage=StageName.REVIEWING,
                request_id=request_id,
                message="Critic requested a rollback.",
                reason=review.reason,
                error_stage=review.error_stage or ReviewErrorStage.UNKNOWN,
                fix_suggestion=review.fix_suggestion,
            ),
        )
        target_node = _rollback_node_for_stage(review.error_stage)
        if error_count > max_error_count or target_node is None:
            failure_message = review.reason
            if error_count > max_error_count:
                failure_message = (
                    f"Workflow aborted after {error_count} errors. Last review: {review.reason}"
                )

            _emit_error(
                event_store,
                session_id=session_id,
                request_id=request_id,
                stage=StageName.FAILED,
                message=failure_message,
                error_code=ErrorCode.REVIEW_REJECTED,
                details={"review": review.model_dump(mode="json")},
            )
            _emit_stage_completed(
                event_store,
                session_id=session_id,
                request_id=request_id,
                stage=StageName.REVIEWING,
                message="Critic completed with terminal failure.",
            )
            return {
                **updates,
                "error_count": error_count,
                "last_error": failure_message,
                "stage": StageName.FAILED,
                "rollback_target": rollback_target,
                "interrupted": False,
            }

        rollback_updates = _clear_state_for_rollback(review.error_stage)
        _emit_stage_completed(
            event_store,
            session_id=session_id,
            request_id=request_id,
            stage=StageName.REVIEWING,
            message=f"Critic completed and rolled back to {target_node}.",
        )
        return {
            **updates,
            **rollback_updates,
            "error_count": error_count,
            "last_error": review.reason,
            "rollback_target": rollback_target,
            "interrupted": False,
        }

    return node


def _route_after_input_guard(state: GraphState) -> str:
    if state["pending_clarification_question"]:
        return "ask_clarification"
    return "orchestrator"


def _route_after_orchestrator(state: GraphState) -> str:
    if state["stage"] == StageName.FAILED:
        return "end"

    decision = state["orchestrator_decision"]
    if decision is None:
        return "ask_clarification"
    if decision.requires_clarification or not decision.selected_nodes:
        return "ask_clarification"

    selected_nodes = set(decision.selected_nodes)
    if NodeName.VISUAL_MAPPER in selected_nodes:
        if NodeName.LOGICIAN not in selected_nodes and state["payload_logic"] is None:
            return "ask_clarification"
        if NodeName.STYLE_CONFIGURATOR not in selected_nodes and state["payload_style"] is None:
            return "ask_clarification"

    if NodeName.LOGICIAN in selected_nodes and NodeName.STYLE_CONFIGURATOR in selected_nodes:
        return "parallel_entry"

    first_node = decision.selected_nodes[0]
    if first_node == NodeName.LOGICIAN:
        return "logician_single"
    if first_node == NodeName.STYLE_CONFIGURATOR:
        return "style_single"
    if first_node == NodeName.VISUAL_MAPPER:
        return "visual_mapper"
    return "ask_clarification"


def _route_after_critic(state: GraphState) -> str:
    if state["stage"] == StageName.FAILED:
        return "end"

    if state["rollback_target"] == ReviewErrorStage.LOGICIAN.value:
        return "logician_single"
    if state["rollback_target"] == ReviewErrorStage.STYLE_CONFIGURATOR.value:
        return "style_single"
    if state["rollback_target"] == ReviewErrorStage.VISUAL_MAPPER.value:
        return "visual_mapper"

    review = state["payload_review"]
    if review is not None and review.passed:
        return "summary"
    return "end"


def _continue_or_end(next_node: str) -> Callable[[GraphState], str]:
    def route(state: GraphState) -> str:
        if state["stage"] == StageName.FAILED:
            return "end"
        return next_node

    return route


def _build_failure_updates(
    event_store: WorkflowEventStore,
    *,
    state: GraphState,
    session_id: str,
    request_id: str,
    stage: StageName,
    message: str,
    exception: Exception,
    max_error_count: int,
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
        details=_error_details_for_exception(exception),
    )
    return {
        "error_count": error_count,
        "last_error": failure_message,
        "stage": StageName.FAILED,
        "needs_clarification": False,
        "interrupted": False,
    }


def _resolve_clarification_question(state: GraphState) -> str:
    if state["pending_clarification_question"]:
        return state["pending_clarification_question"]

    decision = state["orchestrator_decision"]
    if decision is not None and decision.clarification_question:
        return decision.clarification_question
    if decision is not None:
        selected_nodes = set(decision.selected_nodes)
        if NodeName.VISUAL_MAPPER in selected_nodes and state["payload_logic"] is None:
            return "当前会话缺少逻辑结构，请先补充方法流程或重新生成逻辑稿。"
        if NodeName.VISUAL_MAPPER in selected_nodes and state["payload_style"] is None:
            return "当前会话缺少风格方案，请先补充风格要求或重新生成风格稿。"

    return "请补充当前科研绘图任务所需的关键信息。"


def _rollback_node_for_stage(error_stage: ReviewErrorStage | None) -> str | None:
    if error_stage == ReviewErrorStage.LOGICIAN:
        return "logician_single"
    if error_stage == ReviewErrorStage.STYLE_CONFIGURATOR:
        return "style_single"
    if error_stage == ReviewErrorStage.VISUAL_MAPPER:
        return "visual_mapper"
    return None


def _clear_state_for_rollback(error_stage: ReviewErrorStage | None) -> dict[str, Any]:
    if error_stage == ReviewErrorStage.LOGICIAN:
        return {
            "payload_logic": None,
            "payload_mapper": None,
            "payload_review": None,
            "payload_final": None,
        }
    if error_stage == ReviewErrorStage.STYLE_CONFIGURATOR:
        return {
            "payload_style": None,
            "payload_mapper": None,
            "payload_review": None,
            "payload_final": None,
        }
    if error_stage == ReviewErrorStage.VISUAL_MAPPER:
        return {
            "payload_mapper": None,
            "payload_review": None,
            "payload_final": None,
        }
    return {}


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


def _error_details_for_exception(exception: Exception) -> dict[str, Any]:
    if isinstance(exception, DrawAgentError):
        if isinstance(exception.details, dict):
            return exception.details
        return {"details": exception.details}
    return {"exception_type": type(exception).__name__}
