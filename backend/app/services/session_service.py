from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

from app.core.errors import ImageNotReadyError
from app.schemas import ArtifactResponse, SessionStateSummary, TextArtifact
from app.storage import SessionStore, TempFileManager


class SessionService:
    def __init__(
        self,
        *,
        session_store: SessionStore,
        temp_file_manager: TempFileManager,
        session_cleanup_hooks: Iterable[Callable[[str], None]] | None = None,
    ) -> None:
        self.session_store = session_store
        self.temp_file_manager = temp_file_manager
        self.session_cleanup_hooks = list(session_cleanup_hooks or [])

    def create_session(self) -> SessionStateSummary:
        record = self.session_store.create_session()
        self.temp_file_manager.ensure_session_directories(record.session_id)
        return record.to_summary()

    def get_summary(self, session_id: str) -> SessionStateSummary:
        return self.session_store.get_session(session_id).to_summary()

    def delete_session(self, session_id: str) -> tuple[bool, bool]:
        self.session_store.get_session(session_id)
        deleted_record = self.session_store.delete_session(session_id)
        removed_directory = self.temp_file_manager.delete_session_dir(session_id)
        for cleanup_hook in self.session_cleanup_hooks:
            cleanup_hook(session_id)
        return deleted_record is not None, removed_directory

    def get_artifacts(self, session_id: str) -> ArtifactResponse:
        state = self.session_store.get_state(session_id)
        artifacts = state.get("artifacts") or {}
        return ArtifactResponse(
            session_id=session_id,
            logic_artifact=self._resolve_artifact_slot(
                artifacts,
                "logic_artifact",
            ),
            style_artifact=self._resolve_artifact_slot(
                artifacts,
                "style_artifact",
            ),
            plan_review_artifact=self._resolve_artifact_slot(
                artifacts,
                "plan_review_artifact",
            ),
            mapper_artifact=self._resolve_artifact_slot(
                artifacts,
                "mapper_artifact",
            ),
            final_review_artifact=self._resolve_artifact_slot(
                artifacts,
                "final_review_artifact",
            ),
            final_prompt_artifact=self._resolve_artifact_slot(
                artifacts,
                "final_prompt_artifact",
            ),
        )

    def get_download_path(self, session_id: str) -> Path:
        state = self.session_store.get_state(session_id)
        relative_path = (
            state["generated_image_meta"].relative_path
            if state["generated_image_meta"] is not None
            else state["generated_image_path"]
        )
        if not relative_path:
            raise ImageNotReadyError(details={"session_id": session_id})

        resolved_path = self.temp_file_manager.resolve_relative_path(relative_path)
        try:
            resolved_path.relative_to(self.temp_file_manager.base_dir)
        except ValueError as exc:
            raise ImageNotReadyError(
                "Generated image path points outside the temp directory.",
                details={"session_id": session_id},
            ) from exc

        if not resolved_path.exists():
            raise ImageNotReadyError(details={"session_id": session_id, "path": relative_path})
        return resolved_path

    def _resolve_artifact_slot(
        self,
        artifacts: dict[str, TextArtifact | None],
        slot_name: str,
    ) -> TextArtifact | None:
        artifact = artifacts.get(slot_name)
        if artifact is not None:
            return artifact
        return None
