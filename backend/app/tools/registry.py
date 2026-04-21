from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.core.errors import InputValidationError
from app.schemas.common import StageName
from app.schemas.tools import ToolKind


@dataclass(frozen=True)
class ToolRegistration:
    tool_name: str
    kind: ToolKind
    description: str
    parameters_schema: dict[str, Any]
    progress_stage: StageName | None = None
    executor_factory: Callable[[], Any] | None = None


class ToolRegistry:
    def __init__(self) -> None:
        self._registrations: dict[str, ToolRegistration] = {}

    def register(self, registration: ToolRegistration) -> None:
        self._registrations[registration.tool_name] = registration

    def get(self, tool_name: str) -> ToolRegistration:
        registration = self._registrations.get(tool_name)
        if registration is None:
            raise InputValidationError(
                "Unknown tool name.",
                details={"tool_name": tool_name, "available_tools": sorted(self._registrations)},
            )
        return registration

    def as_llm_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": registration.tool_name,
                    "description": registration.description,
                    "parameters": registration.parameters_schema,
                },
            }
            for registration in self._registrations.values()
        ]

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._registrations))
