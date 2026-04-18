from __future__ import annotations

import json
import os

import pytest

from app.core.settings import get_settings
from app.diagnostics import diagnose_image


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_IMAGE_TESTS") != "1",
    reason="Set RUN_LIVE_IMAGE_TESTS=1 to execute real image connectivity checks.",
)


def test_live_image_connectivity() -> None:
    settings = get_settings()
    assert settings.image_provider, "IMAGE_PROVIDER is required for live image connectivity tests."
    assert settings.image_api_key, "IMAGE_API_KEY is required for live image connectivity tests."
    assert settings.image_base_url, "IMAGE_BASE_URL is required for live image connectivity tests."
    assert settings.image_model, "IMAGE_MODEL is required for live image connectivity tests."

    result = diagnose_image(settings=settings)
    assert result["ok"], json.dumps(result, ensure_ascii=False, indent=2)
