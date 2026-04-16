from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class StyleKnowledgeProvider:
    def __init__(self, data_path: Path | None = None) -> None:
        self.data_path = data_path or Path(__file__).resolve().parent / "style_profiles.json"
        self._data = json.loads(self.data_path.read_text(encoding="utf-8"))

    def lookup(
        self,
        *,
        discipline: str | None,
        target_journal: str | None,
        user_feedback: str | None = None,
    ) -> dict[str, Any]:
        merged: dict[str, Any] = dict(self._data["default"])
        matched_profiles: list[str] = [merged.get("profile_name", "default")]

        discipline_key = self._normalize_key(discipline)
        journal_key = self._normalize_key(target_journal)

        discipline_profiles = self._data.get("discipline_profiles", {})
        journal_profiles = self._data.get("journal_profiles", {})

        if discipline_key in discipline_profiles:
            merged = self._merge_profiles(merged, discipline_profiles[discipline_key])
            matched_profiles.append(discipline_profiles[discipline_key].get("profile_name", discipline_key))

        if journal_key in journal_profiles:
            merged = self._merge_profiles(merged, journal_profiles[journal_key])
            matched_profiles.append(journal_profiles[journal_key].get("profile_name", journal_key))

        merged["matched_profiles"] = matched_profiles
        merged["discipline"] = discipline or "unknown"
        merged["target_journal"] = target_journal
        merged["user_feedback"] = user_feedback or ""
        return merged

    def _merge_profiles(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        for key, value in override.items():
            if isinstance(value, list) and isinstance(merged.get(key), list):
                merged[key] = [*merged[key], *value]
            else:
                merged[key] = value
        return merged

    def _normalize_key(self, value: str | None) -> str:
        if not value:
            return ""
        return " ".join(value.strip().lower().replace("-", " ").split())
