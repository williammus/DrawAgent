from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.graph.state import GraphState
from app.schemas.tools import ToolCallSpec, ToolExecutionStatus, ToolExecutionTraceItem
from app.tools.registry import ToolRegistry


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class ToolExecutionOutcome:
    state_updates: dict[str, Any]
    trace_item: ToolExecutionTraceItem
    error: Exception | None = None


class ToolExecutor:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def execute_business_call(
        self,
        state: GraphState,
        tool_call: ToolCallSpec,
    ) -> ToolExecutionOutcome:
        registration = self.registry.get(tool_call.tool_name)
        started_at = utc_now()
        try:
            executor = registration.executor_factory() if registration.executor_factory else None
            if executor is None:
                raise ValueError(f"Tool '{tool_call.tool_name}' has no executor factory.")
            state_updates = executor.run(state)
            return ToolExecutionOutcome(
                state_updates=state_updates,
                trace_item=ToolExecutionTraceItem(
                    call_id=tool_call.call_id,
                    tool_name=tool_call.tool_name,
                    status=ToolExecutionStatus.SUCCEEDED,
                    started_at=started_at,
                    finished_at=utc_now(),
                ),
            )
        except Exception as exc:
            return ToolExecutionOutcome(
                state_updates={},
                trace_item=ToolExecutionTraceItem(
                    call_id=tool_call.call_id,
                    tool_name=tool_call.tool_name,
                    status=ToolExecutionStatus.FAILED,
                    started_at=started_at,
                    finished_at=utc_now(),
                    error=str(exc),
                ),
                error=exc,
            )
