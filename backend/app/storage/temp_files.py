from __future__ import annotations

import shutil
from pathlib import Path


class TempFileManager:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def session_dir(self, session_id: str) -> Path:
        return self.base_dir / session_id

    def uploads_dir(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "uploads"

    def outputs_dir(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "outputs"

    def ensure_session_directories(self, session_id: str) -> tuple[Path, Path]:
        uploads_dir = self.uploads_dir(session_id)
        outputs_dir = self.outputs_dir(session_id)
        uploads_dir.mkdir(parents=True, exist_ok=True)
        outputs_dir.mkdir(parents=True, exist_ok=True)
        return uploads_dir, outputs_dir

    def delete_session_dir(self, session_id: str) -> bool:
        session_dir = self.session_dir(session_id)
        if not session_dir.exists():
            return False
        shutil.rmtree(session_dir)
        return True

    def cleanup_orphaned_directories(self, active_session_ids: set[str]) -> list[str]:
        removed_directories: list[str] = []
        for child in self.base_dir.iterdir():
            if not child.is_dir():
                continue
            if child.name in active_session_ids:
                continue
            shutil.rmtree(child)
            removed_directories.append(child.name)
        return removed_directories
