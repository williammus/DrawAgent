from __future__ import annotations

from types import SimpleNamespace

from app.core.errors import AdapterInvocationError
from app.schemas.common import ErrorCode, StageName
from app.schemas.events import ErrorEvent
from app.graph import WorkflowEventStore
from app.services.generation_service import GenerationService
from app.services.task_manager import SessionTaskManager
from app.storage import SessionStore


def test_record_generation_failure_includes_provider_metadata() -> None:
    session_store = SessionStore(ttl_seconds=1800)
    record = session_store.create_session()
    event_store = WorkflowEventStore()
    image_adapter = SimpleNamespace(
        provider_name="nano-banana2",
        model="gemini-3-pro-image-preview-4k",
    )
    service = GenerationService(
        session_store=session_store,
        event_store=event_store,
        image_adapter=image_adapter,
        task_manager=SessionTaskManager(),
    )

    service._record_generation_failure(
        record.session_id,
        "req-generate-failed",
        AdapterInvocationError(
            "Image adapter invocation failed.",
            details={"request_format": "google_generate_content"},
        ),
    )

    state = session_store.get_state(record.session_id)
    assert state["stage"] == StageName.FAILED
    assert state["last_error"] == "Image adapter invocation failed."

    events = event_store.list_events(record.session_id)
    assert len(events) == 1
    error_event = events[0]
    assert isinstance(error_event, ErrorEvent)
    assert error_event.error_code == ErrorCode.ADAPTER_INVOCATION
    assert error_event.details == {
        "error": "Image adapter invocation failed.",
        "provider": "nano-banana2",
        "model": "gemini-3-pro-image-preview-4k",
        "request_format": "google_generate_content",
    }
