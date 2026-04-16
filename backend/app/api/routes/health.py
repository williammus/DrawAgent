from __future__ import annotations

from fastapi import APIRouter

from app.core.logging import get_request_id
from app.core.settings import get_settings


router = APIRouter(tags=["system"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
        "version": settings.version,
        "request_id": get_request_id(),
    }
