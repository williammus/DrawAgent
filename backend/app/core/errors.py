from __future__ import annotations

from typing import Any

from app.schemas.common import ErrorCode


class DrawAgentError(Exception):
    status_code = 400
    error_code = ErrorCode.INTERNAL_SERVER_ERROR
    default_message = "DrawAgent error."

    def __init__(self, message: str | None = None, *, details: Any | None = None) -> None:
        super().__init__(message or self.default_message)
        self.message = message or self.default_message
        self.details = details


class InputValidationError(DrawAgentError):
    status_code = 400
    error_code = ErrorCode.INPUT_VALIDATION
    default_message = "Input validation failed."


class SessionNotFoundError(DrawAgentError):
    status_code = 404
    error_code = ErrorCode.SESSION_NOT_FOUND
    default_message = "Session not found."


class SessionExpiredError(DrawAgentError):
    status_code = 410
    error_code = ErrorCode.SESSION_EXPIRED
    default_message = "Session expired."


class ResourceConflictError(DrawAgentError):
    status_code = 409
    error_code = ErrorCode.RESOURCE_CONFLICT
    default_message = "Requested resource is busy."


class SessionFileNotFoundError(DrawAgentError):
    status_code = 404
    error_code = ErrorCode.FILE_NOT_FOUND
    default_message = "Session file not found."


class ImageNotReadyError(DrawAgentError):
    status_code = 409
    error_code = ErrorCode.IMAGE_NOT_READY
    default_message = "Generated image is not ready."


class ArtifactValidationError(DrawAgentError):
    status_code = 422
    error_code = ErrorCode.ARTIFACT_VALIDATION
    default_message = "Artifact validation failed."


class PromptRenderError(DrawAgentError):
    status_code = 500
    error_code = ErrorCode.PROMPT_RENDER
    default_message = "Prompt rendering failed."


class LLMInvocationError(DrawAgentError):
    status_code = 502
    error_code = ErrorCode.LLM_INVOCATION
    default_message = "LLM invocation failed."


class ReviewRejectedError(DrawAgentError):
    status_code = 409
    error_code = ErrorCode.REVIEW_REJECTED
    default_message = "Review rejected the generated artifacts."


class AdapterInvocationError(DrawAgentError):
    status_code = 502
    error_code = ErrorCode.ADAPTER_INVOCATION
    default_message = "External adapter invocation failed."
