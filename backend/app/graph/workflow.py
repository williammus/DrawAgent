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
    AskClarificationToolInput,
    ControllerToolCall,
    CriticToolInput,
    ErrorCode,
    IntentType,
    ReviewErrorStage,
    ReviewPhase,
    StageName,
    ToolExecutionResult,
    WorkflowWarning,
    WorkflowWarningType,
)
from app.schemas.events import (
    ClarificationRequiredEvent,
    ErrorEvent,
    PromptReadyEvent,
    ReviewFailedEvent,
    StageCompletedEvent,
    StageStartedEvent,
    WorkflowWarningEvent,
)


NodeHandler = Callable[[GraphState, RunnableConfig], dict[str, Any]]


if TYPE_CHECKING:
    from app.agents.factory import AgentRuntime, ToolRegistry


def build_workflow_app(
    *,
    agent_runtime: AgentRuntime,
    event_store: WorkflowEventStore,
    checkpointer: Any,
    max_error_count: int,
) -> Any:
    builder = StateGraph(GraphState)

    builder.add_node(
        "controller",
        _build_controller_node(agent_runtime, event_store, max_error_count),
    )
    builder.add_node(
        "tool_executor",
        _build_tool_executor_node(agent_runtime, event_store, max_error_count),
    )

    builder.add_edge(START, "controller")
    builder.add_conditional_edges(
        "controller",
        _route_after_controller,
        {
            "tool_executor": "tool_executor",
            "end": END,
        },
    )
    builder.add_conditional_edges(
        "tool_executor",
        _route_after_tool_executor,
        {
            "controller": "controller",
            "end": END,
        },
    )

    return builder.compile(checkpointer=checkpointer)


def _build_controller_node(
    agent_runtime: AgentRuntime,
    event_store: WorkflowEventStore,
    max_error_count: int,
) -> NodeHandler:
    def node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
        session_id = _session_id_from_config(config, state)
        request_id = _request_id_from_config(config)
        working_state = deepcopy(state)

        if working_state["interrupted"] and working_state.get("pending_clarification") is not None:
            clarification = working_state["pending_clarification"]
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
                    question=clarification.question,
                    reason=clarification.reason,
                    missing_fields=clarification.missing_fields,
                ),
            )
            answer = interrupt(
                {
                    "question": clarification.question,
                    "reason": clarification.reason,
                    "missing_fields": clarification.missing_fields,
                }
            )
            working_state["user_feedback"] = str(answer)
            working_state["pending_clarification"] = None
            working_state["needs_clarification"] = False
            working_state["interrupted"] = False
            working_state["stage"] = StageName.PLANNING
            working_state["last_error"] = None
            working_state["input_parse_pending"] = True
            _emit_stage_completed(
                event_store,
                session_id=session_id,
                request_id=request_id,
                stage=StageName.CLARIFYING,
                message="Clarification received.",
            )

        _emit_stage_started(
            event_store,
            session_id=session_id,
            request_id=request_id,
            stage=StageName.PLANNING,
            message="Controller started.",
        )
        try:
            if working_state.get("input_parse_pending"):
                latest_input = _latest_user_input_for_parse(working_state)
                if latest_input:
                    parsed = agent_runtime.controller.parse_context(
                        latest_input=latest_input,
                        state=working_state,
                    )
                    _apply_context_parse(working_state, parsed)
                working_state["input_parse_pending"] = False

            missing_fields = _required_context_fields(working_state)
            if missing_fields:
                clarification_call = _build_context_clarification_call(missing_fields)
                working_state["controller_tool_calls"] = [clarification_call]
                working_state["intent"] = IntentType.CLARIFY
                working_state["last_error"] = None
                _emit_stage_completed(
                    event_store,
                    session_id=session_id,
                    request_id=request_id,
                    stage=StageName.PLANNING,
                    message="Controller requested required context clarification.",
                )
                return _state_diff(state, working_state)

            response = agent_runtime.controller.run(working_state)
            validated_tool_calls = _validate_controller_tool_calls(
                response.tool_calls,
                tool_registry=agent_runtime.tool_registry,
            )
        except Exception as exc:
            return _build_failure_updates(
                event_store,
                state=state,
                session_id=session_id,
                request_id=request_id,
                stage=StageName.PLANNING,
                message="Controller failed.",
                exception=exc,
                failing_node="controller",
                max_error_count=max_error_count,
            )

        working_state["controller_tool_calls"] = validated_tool_calls
        working_state["last_error"] = None
        working_state["stage"] = (
            StageName.PLANNING if validated_tool_calls else working_state["stage"]
        )
        working_state["intent"] = _infer_intent(state, validated_tool_calls)
        _emit_stage_completed(
            event_store,
            session_id=session_id,
            request_id=request_id,
            stage=StageName.PLANNING,
            message=response.assistant_text or "Controller completed.",
        )
        return _state_diff(state, working_state)

    return node


def _build_tool_executor_node(
    agent_runtime: AgentRuntime,
    event_store: WorkflowEventStore,
    max_error_count: int,
) -> NodeHandler:
    def node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
        session_id = _session_id_from_config(config, state)
        request_id = _request_id_from_config(config)
        working_state = deepcopy(state)
        execution_results: list[ToolExecutionResult] = []

        for tool_call in state["controller_tool_calls"]:
            try:
                result = _execute_tool_call(
                    tool_call,
                    working_state=working_state,
                    agent_runtime=agent_runtime,
                    event_store=event_store,
                    session_id=session_id,
                    request_id=request_id,
                )
            except Exception as exc:
                return _build_failure_updates(
                    event_store,
                    state=working_state,
                    session_id=session_id,
                    request_id=request_id,
                    stage=StageName.PLANNING,
                    message=f"{tool_call.tool_name} failed.",
                    exception=exc,
                    failing_node=tool_call.tool_name,
                    max_error_count=max_error_count,
                )

            execution_results.append(result)
            if working_state["stage"] == StageName.FAILED:
                break

        working_state["last_tool_results"] = execution_results
        working_state["controller_tool_calls"] = []
        return _state_diff(state, working_state)

    return node


def _execute_tool_call(
    tool_call: ControllerToolCall,
    *,
    working_state: GraphState,
    agent_runtime: AgentRuntime,
    event_store: WorkflowEventStore,
    session_id: str,
    request_id: str,
) -> ToolExecutionResult:
    definition = agent_runtime.tool_registry.get(tool_call.tool_name)
    if definition.tool_kind == "control":
        return _execute_control_tool_call(
            tool_call,
            working_state=working_state,
            event_store=event_store,
            session_id=session_id,
            request_id=request_id,
        )
    return _execute_business_tool_call(
        tool_call,
        working_state=working_state,
        agent_runtime=agent_runtime,
        event_store=event_store,
        session_id=session_id,
        request_id=request_id,
    )


def _execute_control_tool_call(
    tool_call: ControllerToolCall,
    *,
    working_state: GraphState,
    event_store: WorkflowEventStore,
    session_id: str,
    request_id: str,
) -> ToolExecutionResult:
    action = AskClarificationToolInput.model_validate(tool_call.arguments)
    if working_state["clarification_rounds_in_loop"] >= 2:
        warning = WorkflowWarning(
            warning_type=WorkflowWarningType.CLARIFICATION_LIMIT_REACHED,
            message="Clarification limit reached in the current loop. Continue with best-effort execution.",
            loop_id=working_state["loop_id"],
        )
        working_state["bypass_warnings"] = [*working_state["bypass_warnings"], warning]
        event_store.append(
            session_id,
            WorkflowWarningEvent(
                session_id=session_id,
                stage=StageName.CLARIFYING,
                request_id=request_id,
                message=warning.message,
                warning_type=warning.warning_type,
                loop_id=warning.loop_id,
                review_phase=None,
            ),
        )
        working_state["pending_clarification"] = None
        working_state["needs_clarification"] = False
        working_state["interrupted"] = False
        working_state["stage"] = StageName.PLANNING
        return ToolExecutionResult(
            tool_name=tool_call.tool_name,
            ok=True,
            message=warning.message,
            warning_type=warning.warning_type,
        )

    working_state["clarification_rounds_in_loop"] += 1
    working_state["pending_clarification"] = action
    working_state["needs_clarification"] = True
    working_state["interrupted"] = True
    working_state["stage"] = StageName.CLARIFYING
    return ToolExecutionResult(
        tool_name=tool_call.tool_name,
        ok=True,
        message=action.question,
    )


def _execute_business_tool_call(
    tool_call: ControllerToolCall,
    *,
    working_state: GraphState,
    agent_runtime: AgentRuntime,
    event_store: WorkflowEventStore,
    session_id: str,
    request_id: str,
) -> ToolExecutionResult:
    stage = _stage_for_tool(tool_call.tool_name)
    _emit_stage_started(
        event_store,
        session_id=session_id,
        request_id=request_id,
        stage=stage,
        message=f"{tool_call.tool_name} started.",
    )

    if tool_call.tool_name == "critic_tool":
        result = _handle_critic_gate(
            tool_call=tool_call,
            working_state=working_state,
            agent_runtime=agent_runtime,
            event_store=event_store,
            session_id=session_id,
            request_id=request_id,
        )
    else:
        executor = agent_runtime.tool_factory.create_executor(tool_call.tool_name)
        updates = executor.run(working_state)
        working_state.update(updates)
        result = ToolExecutionResult(
            tool_name=tool_call.tool_name,
            ok=True,
            message=f"{tool_call.tool_name} completed.",
        )

    if tool_call.tool_name == "summary_tool":
        final_prompt_artifact = working_state["artifacts"].get("final_prompt_artifact")
        ready_for_generation = bool(
            final_prompt_artifact is not None
            and final_prompt_artifact.metadata.get("ready_for_generation", True)
        )
        if final_prompt_artifact is not None and ready_for_generation:
            event_store.append(
                session_id,
                PromptReadyEvent(
                    session_id=session_id,
                    stage=StageName.PROMPT_READY,
                    request_id=request_id,
                    message="Final prompt is ready for generation.",
                    prompt_version=final_prompt_artifact.prompt_version,
                    ready_for_generation=ready_for_generation,
                ),
            )

    _emit_stage_completed(
        event_store,
        session_id=session_id,
        request_id=request_id,
        stage=stage,
        message=result.message,
    )
    return result


def _handle_critic_gate(
    *,
    tool_call: ControllerToolCall,
    working_state: GraphState,
    agent_runtime: AgentRuntime,
    event_store: WorkflowEventStore,
    session_id: str,
    request_id: str,
) -> ToolExecutionResult:
    critic_input = CriticToolInput.model_validate(tool_call.arguments)
    working_state["current_review_phase"] = critic_input.review_phase
    executor = agent_runtime.tool_factory.create_executor(tool_call.tool_name)
    subject_order = (
        ["logician", "style_configurator"]
        if critic_input.review_phase == ReviewPhase.POST_PLAN
        else ["visual_mapper"]
    )

    subject_artifacts = [
        executor.review_subject(
            working_state,
            subject_type=subject_type,
            review_phase=critic_input.review_phase,
        )
        for subject_type in subject_order
    ]
    failed_subjects = [
        str(artifact.metadata.get("subject_type"))
        for artifact in subject_artifacts
        if not artifact.metadata.get("passed", False)
    ]
    passed = not failed_subjects

    combined_content = "\n\n".join(artifact.content for artifact in subject_artifacts)
    review_slot = (
        "plan_review_artifact"
        if critic_input.review_phase == ReviewPhase.POST_PLAN
        else "final_review_artifact"
    )
    review_artifact = subject_artifacts[-1].model_copy(
        update={
            "content": combined_content,
            "metadata": {
                "passed": passed,
                "review_phase": critic_input.review_phase,
                "subjects": subject_order,
                "failed_subjects": failed_subjects,
            },
        }
    )
    artifacts = dict(working_state["artifacts"])
    artifacts[review_slot] = review_artifact
    working_state["artifacts"] = artifacts

    if passed:
        return ToolExecutionResult(
            tool_name=tool_call.tool_name,
            ok=True,
            message="Critic passed.",
            review_phase=critic_input.review_phase,
        )

    failure_stage = _review_error_stage_for_subject(failed_subjects[0])
    event_store.append(
        session_id,
        ReviewFailedEvent(
            session_id=session_id,
            stage=StageName.REVIEWING,
            request_id=request_id,
            message="Critic requested a retry.",
            review_phase=critic_input.review_phase,
            reason=combined_content,
            error_stage=failure_stage,
            fix_suggestion=[],
        ),
    )
    counter_key = _review_counter_key(critic_input.review_phase)
    working_state[counter_key] += 1
    if working_state[counter_key] > 2:
        warning = WorkflowWarning(
            warning_type=WorkflowWarningType.REVIEW_LIMIT_REACHED,
            message=(
                f"Review limit reached for phase {critic_input.review_phase}. "
                "Continue with warning bypass."
            ),
            loop_id=working_state["loop_id"],
            review_phase=critic_input.review_phase,
        )
        working_state["bypass_warnings"] = [*working_state["bypass_warnings"], warning]
        working_state["artifacts"][review_slot] = review_artifact.model_copy(
            update={
                "metadata": {
                    **review_artifact.metadata,
                    "passed": True,
                    "warning_bypassed": True,
                }
            }
        )
        event_store.append(
            session_id,
            WorkflowWarningEvent(
                session_id=session_id,
                stage=StageName.REVIEWING,
                request_id=request_id,
                message=warning.message,
                warning_type=warning.warning_type,
                loop_id=warning.loop_id,
                review_phase=warning.review_phase,
            ),
        )
        return ToolExecutionResult(
            tool_name=tool_call.tool_name,
            ok=True,
            message=warning.message,
            review_phase=critic_input.review_phase,
            warning_type=warning.warning_type,
            retry_target=_retry_target_for_failed_subjects(failed_subjects),
        )

    _clear_state_for_retry(working_state, failed_subjects)
    return ToolExecutionResult(
        tool_name=tool_call.tool_name,
        ok=False,
        message=combined_content,
        review_phase=critic_input.review_phase,
        retry_target=_retry_target_for_failed_subjects(failed_subjects),
    )


def _route_after_controller(state: GraphState) -> str:
    if state["stage"] == StageName.FAILED:
        return "end"
    if state["controller_tool_calls"]:
        return "tool_executor"
    return "end"


def _route_after_tool_executor(state: GraphState) -> str:
    if state["stage"] == StageName.FAILED:
        return "end"
    return "controller"


def _stage_for_tool(tool_name: str) -> StageName:
    if tool_name == "logician_tool":
        return StageName.LOGIC_READY
    if tool_name == "style_configurator_tool":
        return StageName.STYLE_READY
    if tool_name == "visual_mapper_tool":
        return StageName.MAPPING_READY
    if tool_name == "critic_tool":
        return StageName.REVIEWING
    if tool_name == "summary_tool":
        return StageName.PROMPT_READY
    return StageName.PLANNING


def _review_counter_key(review_phase: ReviewPhase) -> str:
    if review_phase == ReviewPhase.POST_PLAN:
        return "post_plan_review_rounds_in_loop"
    return "post_mapper_review_rounds_in_loop"


def _clear_state_for_retry(
    state: GraphState,
    failed_subjects: list[str],
) -> None:
    artifacts = dict(state["artifacts"])
    artifacts["final_prompt_artifact"] = None
    if "logician" in failed_subjects:
        artifacts["logic_artifact"] = None
        artifacts["mapper_artifact"] = None
        artifacts["plan_review_artifact"] = None
        artifacts["final_review_artifact"] = None
    if "style_configurator" in failed_subjects:
        artifacts["style_artifact"] = None
        artifacts["mapper_artifact"] = None
        artifacts["plan_review_artifact"] = None
        artifacts["final_review_artifact"] = None
    if "visual_mapper" in failed_subjects:
        artifacts["mapper_artifact"] = None
        artifacts["final_review_artifact"] = None
    state["artifacts"] = artifacts


def _validate_controller_tool_calls(
    tool_calls: list[ControllerToolCall],
    *,
    tool_registry: ToolRegistry,
) -> list[ControllerToolCall]:
    validated: list[ControllerToolCall] = []
    for tool_call in tool_calls:
        definition = tool_registry.get(tool_call.tool_name)
        arguments = definition.input_model.model_validate(tool_call.arguments).model_dump(mode="json")
        validated.append(
            tool_call.model_copy(
                update={
                    "tool_name": definition.tool_name,
                    "arguments": arguments,
                }
            )
        )
    return validated


def _infer_intent(state: GraphState, tool_calls: list[ControllerToolCall]):
    if not tool_calls:
        return state["intent"]
    if state["intent"] not in {IntentType.UNKNOWN, IntentType.CLARIFY}:
        return state["intent"]
    artifacts = state.get("artifacts") or {}
    tool_names = {tool.tool_name for tool in tool_calls}
    if {"logician_tool", "style_configurator_tool"} <= tool_names:
        return (
            IntentType.NEW_TASK
            if state["source_text"] and artifacts.get("logic_artifact") is None
            else IntentType.MODIFY_LOGIC_AND_STYLE
        )
    first_tool = tool_calls[0].tool_name
    if first_tool == "logician_tool":
        return IntentType.MODIFY_LOGIC
    if first_tool == "style_configurator_tool":
        return IntentType.MODIFY_STYLE
    if first_tool == "visual_mapper_tool":
        return IntentType.MODIFY_LAYOUT
    if first_tool == "ask_clarification":
        return IntentType.CLARIFY
    return state["intent"]


def _latest_user_input_for_parse(state: GraphState) -> str:
    if state.get("loop_origin") == "user_feedback":
        return str(state.get("user_feedback") or "")
    if state.get("loop_origin") == "source_text":
        return str(state.get("source_text") or "")
    return str(state.get("user_feedback") or state.get("source_text") or "")


def _apply_context_parse(state: GraphState, parsed: Any) -> None:
    discipline = str(parsed.discipline).strip() if parsed.discipline else ""
    target_venue = str(parsed.target_venue).strip() if parsed.target_venue else ""
    target_venue_type = parsed.target_venue_type

    if discipline:
        state["parsed_discipline"] = discipline
    if target_venue:
        state["parsed_target_venue"] = target_venue
    if target_venue_type:
        state["parsed_target_venue_type"] = target_venue_type

    incoming_requirements = [item.strip() for item in parsed.special_requirements if str(item).strip()]
    if parsed.special_requirements_action == "replace":
        state["parsed_special_requirements"] = incoming_requirements
    elif parsed.special_requirements_action == "append":
        existing = state.get("parsed_special_requirements") or []
        merged: list[str] = []
        for item in [*existing, *incoming_requirements]:
            if item not in merged:
                merged.append(item)
        state["parsed_special_requirements"] = merged


def _required_context_fields(state: GraphState) -> list[str]:
    missing: list[str] = []
    if not (state.get("parsed_discipline") or "").strip():
        missing.append("discipline")
    if not (state.get("parsed_target_venue") or "").strip():
        missing.append("target_venue")
    venue_type = (state.get("parsed_target_venue_type") or "").strip().lower()
    if venue_type in {"", "unknown"}:
        missing.append("target_venue_type")
    return missing


def _build_context_clarification_call(missing_fields: list[str]) -> ControllerToolCall:
    return ControllerToolCall(
        tool_name="ask_clarification",
        arguments={
            "question": "请补充该图所属领域、目标期刊或会议，以及它属于期刊还是会议。",
            "reason": "missing_required_context",
            "missing_fields": missing_fields,
        },
    )


def _review_error_stage_for_subject(subject_type: str) -> ReviewErrorStage:
    if subject_type == "logician":
        return ReviewErrorStage.LOGICIAN
    if subject_type == "style_configurator":
        return ReviewErrorStage.STYLE_CONFIGURATOR
    if subject_type == "visual_mapper":
        return ReviewErrorStage.VISUAL_MAPPER
    return ReviewErrorStage.UNKNOWN


def _retry_target_for_failed_subjects(failed_subjects: list[str]) -> str | None:
    if not failed_subjects:
        return None
    if len(failed_subjects) == 1:
        return failed_subjects[0]
    return "multiple"


def _state_diff(base_state: GraphState, updated_state: GraphState) -> dict[str, Any]:
    diff: dict[str, Any] = {}
    for key, value in updated_state.items():
        if base_state.get(key) != value:
            diff[key] = value
    return diff


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
    return {
        "controller_tool_calls": [],
        "error_count": error_count,
        "interrupted": False,
        "last_error": failure_message,
        "needs_clarification": False,
        "pending_clarification": None,
        "stage": StageName.FAILED,
    }


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
