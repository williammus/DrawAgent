from __future__ import annotations

from enum import StrEnum


class StageName(StrEnum):
    IDLE = "idle"
    CLARIFYING = "clarifying"
    PLANNING = "planning"
    LOGIC_READY = "logic_ready"
    STYLE_READY = "style_ready"
    MAPPING_READY = "mapping_ready"
    REVIEWING = "reviewing"
    PROMPT_READY = "prompt_ready"
    GENERATING_IMAGE = "generating_image"
    COMPLETED = "completed"
    FAILED = "failed"


class IntentType(StrEnum):
    UNKNOWN = "unknown"
    NEW_TASK = "new_task"
    MODIFY_LOGIC = "modify_logic"
    MODIFY_STYLE = "modify_style"
    MODIFY_LAYOUT = "modify_layout"
    MODIFY_LOGIC_AND_STYLE = "modify_logic_and_style"
    CLARIFY = "clarify"


class ReviewErrorStage(StrEnum):
    INPUT_GUARD = "input_guard"
    ORCHESTRATOR = "orchestrator"
    LOGICIAN = "logician"
    STYLE_CONFIGURATOR = "style_configurator"
    VISUAL_MAPPER = "visual_mapper"
    CRITIC = "critic"
    SUMMARY_AGENT = "summary_agent"
    IMAGE_ADAPTER = "image_adapter"
    UNKNOWN = "unknown"


class EventType(StrEnum):
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    CLARIFICATION_REQUIRED = "clarification_required"
    REVIEW_FAILED = "review_failed"
    PROMPT_READY = "prompt_ready"
    IMAGE_GENERATED = "image_generated"
    ERROR = "error"


class ErrorCode(StrEnum):
    INPUT_VALIDATION = "input_validation_error"
    SESSION_NOT_FOUND = "session_not_found"
    SESSION_EXPIRED = "session_expired"
    ARTIFACT_VALIDATION = "artifact_validation_error"
    REVIEW_REJECTED = "review_rejected"
    ADAPTER_INVOCATION = "adapter_invocation_error"
    HTTP_ERROR = "http_error"
    REQUEST_VALIDATION = "request_validation_error"
    INTERNAL_SERVER_ERROR = "internal_server_error"
