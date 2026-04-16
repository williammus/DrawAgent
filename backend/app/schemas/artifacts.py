from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import IntentType, ReviewErrorStage, StageName


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LogicContainer(StrictModel):
    container_id: str
    name: str
    description: str | None = None
    children: list[str] = Field(default_factory=list)


class LogicNode(StrictModel):
    node_id: str
    label: str
    description: str | None = None
    node_type: str | None = None


class LogicEdge(StrictModel):
    source: str
    target: str
    label: str | None = None
    relation: str | None = None


class LogicSpec(StrictModel):
    chart_title: str
    core_method_summary: str
    containers: list[LogicContainer] = Field(default_factory=list)
    nodes: list[LogicNode] = Field(default_factory=list)
    edges: list[LogicEdge] = Field(default_factory=list)


class StyleSpec(StrictModel):
    discipline: str
    target_journal: str | None = None
    primary_palette: list[str] = Field(default_factory=list)
    secondary_palette: list[str] = Field(default_factory=list)
    font_family: str
    line_style: str
    node_shape_rules: dict[str, str] = Field(default_factory=dict)
    layout_style: str
    legend_style: str
    forbidden_visual_elements: list[str] = Field(default_factory=list)
    style_keywords: list[str] = Field(default_factory=list)


class MapperSpec(StrictModel):
    narrative_direction: str
    section_layout: list[str] = Field(default_factory=list)
    module_positions: dict[str, str] = Field(default_factory=dict)
    grouping_strategy: str
    edge_style_mapping: dict[str, str] = Field(default_factory=dict)
    visual_hierarchy: list[str] = Field(default_factory=list)
    annotation_strategy: str
    legend_placement: str | None = None


class ReviewSpec(StrictModel):
    passed: bool
    error_stage: ReviewErrorStage | None = None
    reason: str
    fix_suggestion: list[str] = Field(default_factory=list)


class FinalPromptSpec(StrictModel):
    final_prompt_en: str
    final_prompt_cn: str
    prompt_version: str
    generation_notes: list[str] = Field(default_factory=list)
    ready_for_generation: bool


class StoredFileMeta(StrictModel):
    file_id: str
    original_name: str
    stored_name: str
    media_type: str
    size_bytes: int = Field(ge=0)
    relative_path: str
    uploaded_at: datetime = Field(default_factory=utc_now)


class GeneratedImageMeta(StrictModel):
    file_name: str
    media_type: str
    size_bytes: int = Field(ge=0)
    relative_path: str
    provider: str = "nano-banana2"
    generated_at: datetime = Field(default_factory=utc_now)


class SessionStateSummary(StrictModel):
    session_id: str
    stage: StageName
    intent: IntentType
    has_payload_logic: bool
    has_payload_style: bool
    has_payload_mapper: bool
    has_payload_review: bool
    has_payload_final: bool
    needs_clarification: bool
    user_confirmed: bool
    error_count: int = Field(ge=0)
    updated_at: datetime
    expires_at: datetime


class CleanupReport(StrictModel):
    ran_at: datetime = Field(default_factory=utc_now)
    removed_sessions: list[str] = Field(default_factory=list)
    removed_directories: list[str] = Field(default_factory=list)
    failed_targets: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
