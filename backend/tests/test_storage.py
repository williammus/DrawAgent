from datetime import timedelta
from pathlib import Path
from shutil import rmtree
from uuid import uuid4

import pytest

from app.core.errors import SessionExpiredError, SessionNotFoundError
from app.graph.state import build_initial_graph_state
from app.schemas.common import IntentType
from app.storage import CleanupService, SessionStore, TempFileManager
from app.storage.session_store import utc_now


TEST_TEMP_ROOT = Path(__file__).resolve().parents[1] / ".test_tmp"
TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)


def make_temp_dir(name: str) -> Path:
    path = TEST_TEMP_ROOT / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_session_store_create_update_touch_and_delete() -> None:
    store = SessionStore(ttl_seconds=30)
    record = store.create_session("session-1")

    assert record.session_id == "session-1"
    assert record.to_summary().intent == IntentType.UNKNOWN

    state = build_initial_graph_state("session-1")
    state["intent"] = IntentType.NEW_TASK
    updated = store.update_state("session-1", state)

    assert updated.state["intent"] == IntentType.NEW_TASK

    touched = store.touch_session("session-1")
    assert touched.expires_at > touched.updated_at

    deleted = store.delete_session("session-1")
    assert deleted is not None

    with pytest.raises(SessionNotFoundError):
        store.get_session("session-1")


def test_session_store_marks_expired_sessions() -> None:
    store = SessionStore(ttl_seconds=1)
    record = store.create_session("session-expired")
    record.expires_at = utc_now() - timedelta(seconds=1)

    with pytest.raises(SessionExpiredError):
        store.get_session("session-expired")


def test_cleanup_service_purges_expired_session_directories() -> None:
    temp_dir = make_temp_dir("storage-cleanup")
    try:
        store = SessionStore(ttl_seconds=1)
        temp_manager = TempFileManager(temp_dir)
        cleanup_service = CleanupService(store, temp_manager)

        record = store.create_session("session-cleanup")
        temp_manager.ensure_session_directories(record.session_id)
        record.expires_at = utc_now() - timedelta(seconds=1)

        report = cleanup_service.purge_expired_sessions()

        assert report.removed_sessions == ["session-cleanup"]
        assert report.removed_directories == ["session-cleanup"]
        assert not temp_manager.session_dir("session-cleanup").exists()
    finally:
        rmtree(temp_dir, ignore_errors=True)


def test_cleanup_service_removes_orphan_directories() -> None:
    temp_dir = make_temp_dir("storage-orphan")
    try:
        store = SessionStore(ttl_seconds=30)
        temp_manager = TempFileManager(temp_dir)
        cleanup_service = CleanupService(store, temp_manager)

        temp_manager.ensure_session_directories("orphan-session")
        report = cleanup_service.cleanup_orphaned_directories()

        assert report.removed_directories == ["orphan-session"]
        assert not temp_manager.session_dir("orphan-session").exists()
    finally:
        rmtree(temp_dir, ignore_errors=True)


def test_cleanup_service_runs_session_cleanup_hooks() -> None:
    temp_dir = make_temp_dir("storage-hook")
    try:
        cleared_sessions: list[str] = []
        store = SessionStore(ttl_seconds=1)
        temp_manager = TempFileManager(temp_dir)
        cleanup_service = CleanupService(
            store,
            temp_manager,
            session_cleanup_hooks=[cleared_sessions.append],
        )

        record = store.create_session("session-hook")
        temp_manager.ensure_session_directories(record.session_id)
        record.expires_at = utc_now() - timedelta(seconds=1)

        cleanup_service.purge_expired_sessions()

        assert cleared_sessions == ["session-hook"]
    finally:
        rmtree(temp_dir, ignore_errors=True)
