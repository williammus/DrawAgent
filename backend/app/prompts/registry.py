from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.errors import InputValidationError


PROMPT_ROOT = Path(__file__).resolve().parent


PROMPT_MANIFEST: dict[str, dict[str, str]] = {
    "orchestrator": {"v1": "orchestrator/v1.md"},
    "logician": {"v2_json": "logician/v2_json.md"},
    "style_configurator": {"v1": "style_configurator/v1.md"},
    "visual_mapper": {"v1": "visual_mapper/v1.md"},
    "critic": {"v1": "critic/v1.md"},
    "summary": {"v1": "summary/v1.md"},
}

DEFAULT_PROMPT_VERSIONS: dict[str, str] = {
    "orchestrator": "v1",
    "logician": "v2_json",
    "style_configurator": "v1",
    "visual_mapper": "v1",
    "critic": "v1",
    "summary": "v1",
}


@dataclass(frozen=True)
class PromptAsset:
    agent_name: str
    version: str
    path: Path

    def load_text(self) -> str:
        return self.path.read_text(encoding="utf-8")


class PromptRegistry:
    def __init__(
        self,
        prompt_manifest: dict[str, dict[str, str]] | None = None,
        default_versions: dict[str, str] | None = None,
        prompt_root: Path | None = None,
    ) -> None:
        self.prompt_manifest = prompt_manifest or PROMPT_MANIFEST
        self.default_versions = default_versions or DEFAULT_PROMPT_VERSIONS
        self.prompt_root = prompt_root or PROMPT_ROOT

    def get(self, agent_name: str, version: str | None = None) -> PromptAsset:
        if agent_name not in self.prompt_manifest:
            raise InputValidationError(
                f"Unknown prompt agent: {agent_name}.",
                details={"agent_name": agent_name},
            )

        resolved_version = version or self.default_versions[agent_name]
        version_map = self.prompt_manifest[agent_name]
        if resolved_version not in version_map:
            raise InputValidationError(
                f"Unknown prompt version for agent {agent_name}.",
                details={
                    "agent_name": agent_name,
                    "version": resolved_version,
                    "available_versions": sorted(version_map),
                },
            )

        path = self.prompt_root / version_map[resolved_version]
        return PromptAsset(agent_name=agent_name, version=resolved_version, path=path)

    def load_text(self, agent_name: str, version: str | None = None) -> str:
        return self.get(agent_name, version).load_text()

    def available_versions(self, agent_name: str) -> tuple[str, ...]:
        if agent_name not in self.prompt_manifest:
            raise InputValidationError(
                f"Unknown prompt agent: {agent_name}.",
                details={"agent_name": agent_name},
            )

        return tuple(sorted(self.prompt_manifest[agent_name]))
