from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _slugify(value: str, fallback: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", (value or "").strip()).strip("_").lower()
    return text or fallback


class MessageEnvelope(StrictModel):
    id: str
    from_role: str
    to_role: str
    message_type: str
    status: Literal["pending", "processed"] = "pending"
    task_id: str | None = None
    task_type: str | None = None
    summary: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class VirtualTask(StrictModel):
    task_id: str
    task_type: Literal[
        "logic_extraction",
        "style_extraction",
        "visual_mapping",
        "summarization",
        "image_generation",
    ]
    agent_name: str
    output_ref: str
    review_required: bool = True
    review_phase: str | None = None
    retry_count: int = 0
    max_retry: int = 3
    revision_mode: bool = False
    revision_context: dict[str, Any] = Field(default_factory=dict)


class TextArtifactEnvelope(StrictModel):
    key: str
    value: str = ""


class LogicArtifactEnvelope(TextArtifactEnvelope):
    key: Literal["logician"] = "logician"
    value: str = ""


class StyleArtifactEnvelope(TextArtifactEnvelope):
    key: Literal["style_designer"] = "style_designer"
    value: str = ""


class MapperArtifactEnvelope(TextArtifactEnvelope):
    key: Literal["visual_mapper"] = "visual_mapper"
    value: str = ""


class FinalArtifactEnvelope(TextArtifactEnvelope):
    key: Literal["summarizer"] = "summarizer"
    value: str = ""


class ImageArtifactValue(StrictModel):
    image_url: str = ""
    image_b64: str = ""
    image_mime_type: str = ""
    revised_prompt: str = ""
    local_path: str = ""
    public_url: str = ""
    image_attempt_id: str = ""
    provider_request_id: str = ""
    provider_request_path: str = ""
    provider_request_url: str = ""
    provider_request_headers: dict[str, str] = Field(default_factory=dict)
    provider_status_code: int = 0
    provider_started_at: str = ""
    provider_finished_at: str = ""
    provider_duration_ms: int = 0


class ImageArtifactEnvelope(StrictModel):
    key: Literal["image_generator"] = "image_generator"
    value: ImageArtifactValue


class ReviewVerdict(StrictModel):
    approved: bool
    blocking: bool = False
    retry_targets: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    notes: str = ""
