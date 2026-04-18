from __future__ import annotations

import json
import os

import pytest

from app.core.settings import get_settings
from app.diagnostics import diagnose_llm


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_LLM_TESTS") != "1",
    reason="Set RUN_LIVE_LLM_TESTS=1 to execute real LLM connectivity checks.",
)


def test_live_llm_connectivity() -> None:
    settings = get_settings()
    assert settings.llm_api_key, "LLM_API_KEY is required for live LLM connectivity tests."
    assert settings.llm_base_url, "LLM_BASE_URL is required for live LLM connectivity tests."
    assert settings.llm_model, "LLM_MODEL is required for live LLM connectivity tests."

    result = diagnose_llm(settings=settings)
    assert result["ok"], json.dumps(result, ensure_ascii=False, indent=2)
