from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Callable, Iterable
from uuid import uuid4

from fastapi import UploadFile

from app.core.errors import ImageNotReadyError, InputValidationError, SessionFileNotFoundError
from app.graph.state import GraphState
from app.schemas import ArtifactResponse, SessionStateSummary, StoredFileMeta
from app.storage import SessionStore, TempFileManager


class SessionService:
    def __init__(
        self,
        *,
        session_store: SessionStore,
        temp_file_manager: TempFileManager,
        max_session_files: int,
        max_session_file_size_mb: int,
        session_cleanup_hooks: Iterable[Callable[[str], None]] | None = None,
    ) -> None:
        self.session_store = session_store
        self.temp_file_manager = temp_file_manager
        self.max_session_files = max_session_files
        self.max_session_file_size_bytes = max_session_file_size_mb * 1024 * 1024
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
        return ArtifactResponse(
            session_id=session_id,
            payload_logic=state["payload_logic"],
            payload_style=state["payload_style"],
            payload_mapper=state["payload_mapper"],
            payload_review=state["payload_review"],
            payload_final=state["payload_final"],
        )

    async def store_uploads(self, session_id: str, files: list[UploadFile]) -> list[StoredFileMeta]:
        record = self.session_store.get_session(session_id)
        state = self._copy_state(record.state)
        uploaded_files = list(state["uploaded_files"])
        created_files: list[StoredFileMeta] = []
        incoming_count = len(files)
        if not files:
            raise InputValidationError("At least one file is required for upload.")
        if len(uploaded_files) + incoming_count > self.max_session_files:
            raise InputValidationError(
                "Session file limit exceeded.",
                details={
                    "session_id": session_id,
                    "max_session_files": self.max_session_files,
                },
            )

        for upload in files:
            original_name = upload.filename or "upload.bin"
            payload = await upload.read()
            size_bytes = len(payload)
            if size_bytes > self.max_session_file_size_bytes:
                raise InputValidationError(
                    "Uploaded file exceeds size limit.",
                    details={
                        "session_id": session_id,
                        "file_name": original_name,
                        "max_size_bytes": self.max_session_file_size_bytes,
                    },
                )

            stored_name, stored_path = self.temp_file_manager.build_upload_path(session_id, original_name)
            stored_path.write_bytes(payload)
            created_files.append(
                StoredFileMeta(
                    file_id=uuid4().hex,
                    original_name=original_name,
                    stored_name=stored_name,
                    media_type=upload.content_type or "application/octet-stream",
                    size_bytes=size_bytes,
                    relative_path=self.temp_file_manager.relative_path(stored_path),
                )
            )
            uploaded_files.append(created_files[-1])

        state["uploaded_files"] = uploaded_files
        state["source_files"] = list(uploaded_files)
        self.session_store.update_state(session_id, state)
        return created_files

    def delete_upload(self, session_id: str, file_id: str) -> StoredFileMeta:
        record = self.session_store.get_session(session_id)
        state = self._copy_state(record.state)
        uploaded_files = list(state["uploaded_files"])
        target = next((item for item in uploaded_files if item.file_id == file_id), None)
        if target is None:
            raise SessionFileNotFoundError(details={"session_id": session_id, "file_id": file_id})

        state["uploaded_files"] = [item for item in uploaded_files if item.file_id != file_id]
        state["source_files"] = [
            item for item in state["source_files"] if item.file_id != file_id
        ]
        self.session_store.update_state(session_id, state)

        file_path = self.temp_file_manager.resolve_relative_path(target.relative_path)
        try:
            if file_path.exists():
                file_path.unlink()
        except OSError as exc:
            raise InputValidationError(
                "Failed to delete uploaded file from disk.",
                details={"session_id": session_id, "file_id": file_id, "error": str(exc)},
            ) from exc

        return target

    def resolve_attachments(self, session_id: str, attachment_ids: list[str]) -> list[StoredFileMeta]:
        record = self.session_store.get_session(session_id)
        uploaded_files = list(record.state["uploaded_files"])
        if not attachment_ids:
            return uploaded_files

        available = {item.file_id: item for item in uploaded_files}
        missing_ids = [file_id for file_id in attachment_ids if file_id not in available]
        if missing_ids:
            raise SessionFileNotFoundError(
                "One or more attachment ids are invalid.",
                details={"session_id": session_id, "missing_file_ids": missing_ids},
            )
        return [available[file_id] for file_id in attachment_ids]

    def set_active_source_files(self, session_id: str, selected_files: list[StoredFileMeta]) -> GraphState:
        record = self.session_store.get_session(session_id)
        state = self._copy_state(record.state)
        state["source_files"] = list(selected_files)
        research_context = dict(state["research_context"] or {})
        research_context["selected_attachment_ids"] = [item.file_id for item in selected_files]
        state["research_context"] = research_context
        self.session_store.update_state(session_id, state)
        return state

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

    def _copy_state(self, state: GraphState) -> GraphState:
        return deepcopy(state)
