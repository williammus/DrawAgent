from __future__ import annotations

from importlib import import_module
from typing import Any


__all__ = [
    "GraphState",
    "StoredEvent",
    "WorkflowCheckpointStore",
    "WorkflowEventStore",
    "WorkflowRunner",
    "build_initial_graph_state",
    "build_workflow_app",
]


def __getattr__(name: str) -> Any:
    if name in {"GraphState", "build_initial_graph_state"}:
        module = import_module("app.graph.state")
        return getattr(module, name)
    if name in {"StoredEvent", "WorkflowCheckpointStore", "WorkflowEventStore"}:
        module = import_module("app.graph.stores")
        return getattr(module, name)
    if name == "WorkflowRunner":
        module = import_module("app.graph.runner")
        return getattr(module, name)
    if name == "build_workflow_app":
        module = import_module("app.graph.workflow")
        return getattr(module, name)
    raise AttributeError(name)
