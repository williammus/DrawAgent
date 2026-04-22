import pytest
from pydantic import ValidationError

from app.schemas.artifacts import (
    ClarificationAction,
    TextArtifact,
    WorkflowWarning,
)
from app.schemas.api import ChatResumeRequest, ChatRunRequest
from app.schemas.common import ReviewErrorStage, ReviewPhase, WorkflowWarningType
from app.schemas.events import ReviewFailedEvent, WorkflowWarningEvent


def test_review_failed_event_uses_discriminated_payload() -> None:
    event = ReviewFailedEvent(
        session_id="session-1",
        stage="reviewing",
        request_id="req-1",
        message="Review failed.",
        review_phase=ReviewPhase.POST_MAPPER,
        reason="Missing legend placement.",
        error_stage=ReviewErrorStage.STYLE_CONFIGURATOR,
        fix_suggestion=["Add legend placement guidance."],
    )

    assert event.event_type == "review_failed"
    assert event.review_phase == ReviewPhase.POST_MAPPER
    assert event.error_stage == ReviewErrorStage.STYLE_CONFIGURATOR


def test_new_contract_schemas_accept_valid_payloads() -> None:
    artifact = TextArtifact(
        tool_name="summary",
        content="Final prompt content",
        prompt_version="v2",
    )
    clarification = ClarificationAction(
        question="Please provide the abstract.",
        reason="missing_source_text",
        missing_fields=["source_text"],
    )
    warning = WorkflowWarning(
        warning_type=WorkflowWarningType.REVIEW_LIMIT_REACHED,
        message="Review limit reached.",
        loop_id="loop-1",
        review_phase=ReviewPhase.POST_PLAN,
    )
    event = WorkflowWarningEvent(
        session_id="session-1",
        stage="reviewing",
        request_id="req-2",
        message="Review limit reached.",
        warning_type=WorkflowWarningType.REVIEW_LIMIT_REACHED,
        loop_id="loop-1",
        review_phase=ReviewPhase.POST_PLAN,
    )

    assert artifact.tool_name == "summary"
    assert clarification.missing_fields == ["source_text"]
    assert warning.review_phase == ReviewPhase.POST_PLAN
    assert event.event_type == "workflow_warning"


def test_chat_run_request_requires_exactly_one_input() -> None:
    request = ChatRunRequest(session_id="session-1", source_text="paper")

    assert request.source_text == "paper"

    with pytest.raises(ValidationError):
        ChatRunRequest(session_id="session-1", source_text="paper", user_feedback="feedback")

    with pytest.raises(ValidationError):
        ChatRunRequest(session_id="session-1")


def test_chat_resume_request_requires_feedback() -> None:
    request = ChatResumeRequest(session_id="session-1", user_feedback="clarification")

    assert request.user_feedback == "clarification"
