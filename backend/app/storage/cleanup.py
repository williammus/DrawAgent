from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Iterable

from app.schemas.artifacts import CleanupReport
from app.storage.session_store import SessionStore
from app.storage.temp_files import TempFileManager


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CleanupService:
    def __init__(
        self,
        session_store: SessionStore,
        temp_file_manager: TempFileManager,
        session_cleanup_hooks: Iterable[Callable[[str], None]] | None = None,
    ) -> None:
        self.session_store = session_store
        self.temp_file_manager = temp_file_manager
        self.session_cleanup_hooks = list(session_cleanup_hooks or [])

    def purge_expired_sessions(self) -> CleanupReport:
        report = CleanupReport(ran_at=utc_now())
        expired_session_ids = self.session_store.purge_expired(now=report.ran_at)
        report.removed_sessions.extend(expired_session_ids)

        for session_id in expired_session_ids:
            try:
                if self.temp_file_manager.delete_session_dir(session_id):
                    report.removed_directories.append(session_id)
            except OSError:
                report.failed_targets.append(session_id)

            for cleanup_hook in self.session_cleanup_hooks:
                try:
                    cleanup_hook(session_id)
                except Exception:
                    report.failed_targets.append(f"hook:{session_id}")
        return report

    def cleanup_orphaned_directories(self) -> CleanupReport:
        report = CleanupReport(ran_at=utc_now())
        active_session_ids = self.session_store.active_session_ids()
        try:
            report.removed_directories.extend(
                self.temp_file_manager.cleanup_orphaned_directories(active_session_ids)
            )
        except OSError as exc:
            report.failed_targets.append(str(exc))
        return report
