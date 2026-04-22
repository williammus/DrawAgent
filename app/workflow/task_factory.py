from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from app.core.models import VirtualTask


OUTPUT_REF_MAP = {
    "logic_extraction": "payload_logic",
    "style_extraction": "payload_style",
    "visual_mapping": "payload_mapper",
    "summarization": "payload_final",
    "image_generation": "image_result",
}


def completed_stage_names(completed_tasks: list[dict[str, Any]]) -> list[str]:
    return [str(item.get("task_type")) for item in completed_tasks]


def next_skill_stage(
    skill_plan: list[dict[str, Any]],
    completed_tasks: list[dict[str, Any]],
    *,
    include_image_generation: bool = False,
) -> dict[str, Any] | None:
    completed = set(completed_stage_names(completed_tasks))
    for stage in skill_plan:
        stage_name = str(stage.get("stage") or "")
        if stage_name == "image_generation" and not include_image_generation:
            continue
        if stage_name not in completed:
            return deepcopy(stage)
    return None


def build_virtual_task(
    *,
    stage_spec: dict[str, Any],
    max_retry: int,
    retry_count: int = 0,
    revision_mode: bool = False,
    revision_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    task_type = str(stage_spec.get("stage"))
    task = VirtualTask(
        task_id=str(uuid4()),
        task_type=task_type,
        agent_name=str(stage_spec.get("agent_name") or task_type),
        output_ref=OUTPUT_REF_MAP[task_type],
        review_required=bool(stage_spec.get("review_required", True)),
        review_phase=stage_spec.get("review_phase"),
        retry_count=retry_count,
        max_retry=max_retry,
        revision_mode=revision_mode,
        revision_context=revision_context or {},
    )
    return task.model_dump()

