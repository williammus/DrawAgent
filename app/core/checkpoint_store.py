from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CheckpointStore:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, checkpoint_id: str) -> Path:
        return self.root_dir / f"{checkpoint_id}.json"

    def save(self, checkpoint_id: str, payload: dict[str, Any]) -> str:
        path = self._path(checkpoint_id)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        return str(path)

    def load(self, checkpoint_id: str) -> dict[str, Any]:
        path = self._path(checkpoint_id)
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

