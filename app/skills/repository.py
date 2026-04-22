from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    description: str
    plan: list[dict[str, Any]]
    body: str
    file_path: Path

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "stage_count": len(self.plan),
            "file_path": str(self.file_path),
        }


class SkillRepository:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.skills_dir = root_dir / "skills"
        self._skills = self._load()

    def _load(self) -> dict[str, SkillDefinition]:
        skills: dict[str, SkillDefinition] = {}
        for path in sorted(self.skills_dir.glob("*/SKILL.md")):
            raw = path.read_text(encoding="utf-8")
            if raw.startswith("---"):
                _, frontmatter, body = raw.split("---", 2)
                data = yaml.safe_load(frontmatter) or {}
            else:
                data = {}
                body = raw
            skills[str(data.get("name") or path.parent.name)] = SkillDefinition(
                name=str(data.get("name") or path.parent.name),
                description=str(data.get("description") or ""),
                plan=list((data.get("plan") or {}).get("stages", [])),
                body=body.strip(),
                file_path=path,
            )
        return skills

    def get(self, skill_name: str) -> SkillDefinition:
        return self._skills[skill_name]

    def list(self) -> list[SkillDefinition]:
        return list(self._skills.values())

    def describe(self) -> list[dict[str, Any]]:
        return [item.summary() for item in self.list()]

