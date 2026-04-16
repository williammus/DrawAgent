from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.errors import DrawAgentError
from app.core.logging import get_request_id
from app.schemas.common import ErrorCode


logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DrawAgentError)
    async def drawagent_exception_handler(_: Request, exc: DrawAgentError) -> JSONResponse:
        logger.warning("Handled DrawAgent error: %s", exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details,
                    "request_id": get_request_id(),
                }
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": ErrorCode.HTTP_ERROR,
                    "message": exc.detail,
                    "details": {"status_code": exc.status_code},
                    "request_id": get_request_id(),
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": ErrorCode.REQUEST_VALIDATION,
                    "message": "Request validation failed.",
                    "details": exc.errors(),
                    "request_id": get_request_id(),
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": ErrorCode.INTERNAL_SERVER_ERROR,
                    "message": "Internal server error.",
                    "details": {"exception_type": type(exc).__name__},
                    "request_id": get_request_id(),
                }
            },
        )
