from __future__ import annotations

from pathlib import Path
from shutil import rmtree
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.core.errors import AdapterInvocationError
from app.diagnostics import diagnose_image, diagnose_llm
from app.image import MockImageAdapter, OpenAICompatibleImageAdapter
from app.llm import LLMClient
from app.storage import TempFileManager


TEST_TEMP_ROOT = Path("backend/.test_tmp").resolve()
TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)


class FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)

    def create(self, **kwargs):
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeOpenAIClient:
    def __init__(self, responses):
        self.chat = SimpleNamespace(completions=FakeCompletions(responses))


class FailingImageAdapter:
    provider_name = "nano-banana2"
    base_url = "https://example.com/v1"
    model = "qwen-image"

    def generate(self, session_id: str, prompt_text: str):
        raise AdapterInvocationError(
            "Image adapter invocation failed.",
            details={
                "provider": self.provider_name,
                "model": self.model,
                "error": "401 Unauthorized",
            },
        )


def make_temp_dir(prefix: str) -> Path:
    path = TEST_TEMP_ROOT / f"{prefix}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def make_response(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def test_diagnose_llm_reports_success_with_fake_client() -> None:
    client = LLMClient(
        model="test-model",
        base_url="https://example.com/v1",
        client=FakeOpenAIClient([make_response('{"ok": true, "ping": "pong"}')]),
    )

    result = diagnose_llm(llm_client=client)

    assert result["ok"] is True
    assert result["model"] == "test-model"
    assert result["base_url"] == "https://example.com/v1"
    assert "ok" in result["response_keys"]


def test_diagnose_image_reports_mock_configuration_without_external_call() -> None:
    temp_dir = make_temp_dir("diag-mock-image")
    try:
        result = diagnose_image(
            image_adapter=MockImageAdapter(TempFileManager(temp_dir)),
            temp_file_manager=TempFileManager(temp_dir),
        )
    finally:
        rmtree(temp_dir, ignore_errors=True)

    assert result["ok"] is True
    assert result["provider"] == "mock"
    assert "no external image request" in result["note"].lower()


def test_diagnose_image_reports_adapter_failures() -> None:
    temp_dir = make_temp_dir("diag-failing-image")
    try:
        result = diagnose_image(
            image_adapter=FailingImageAdapter(),
            temp_file_manager=TempFileManager(temp_dir),
        )
    finally:
        rmtree(temp_dir, ignore_errors=True)

    assert result["ok"] is False
    assert result["provider"] == "nano-banana2"
    assert result["model"] == "qwen-image"
    assert result["error_code"] == "adapter_invocation_error"
    assert result["details"]["error"] == "401 Unauthorized"


def test_diagnose_image_includes_request_preview_for_openai_adapter() -> None:
    temp_dir = make_temp_dir("diag-openai-image")
    try:
        response = SimpleNamespace(
            data=[SimpleNamespace(b64_json="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8Xw8AAoMBgQf6D2sAAAAASUVORK5CYII=")]
        )
        adapter = OpenAICompatibleImageAdapter(
            api_key="secret",
            base_url="https://example.com/v1",
            model="qwen-image",
            timeout_seconds=30,
            temp_file_manager=TempFileManager(temp_dir),
            client=SimpleNamespace(images=SimpleNamespace(generate=lambda **kwargs: response)),
        )

        result = diagnose_image(
            image_adapter=adapter,
            temp_file_manager=TempFileManager(temp_dir),
        )
    finally:
        rmtree(temp_dir, ignore_errors=True)

    assert result["ok"] is True
    assert result["request_preview"]["method"] == "POST"
    assert result["request_preview"]["url"] == "https://example.com/v1/images/generations"
    assert result["request_preview"]["headers"]["authorization"] == "Bearer <redacted>"
    assert result["request_preview"]["body"]["model"] == "qwen-image"


def test_diagnose_image_includes_request_preview_for_google_native_adapter() -> None:
    temp_dir = make_temp_dir("diag-google-image")
    try:
        adapter = OpenAICompatibleImageAdapter(
            api_key="secret",
            base_url="https://example.com/v1",
            model="gemini-3-pro-image-preview-4k",
            timeout_seconds=30,
            temp_file_manager=TempFileManager(temp_dir),
        )

        with patch.object(
            adapter,
            "generate",
            side_effect=AdapterInvocationError(
                "Image adapter invocation failed.",
                details={"request_format": "google_generate_content"},
            ),
        ):
            preview = diagnose_image(
                image_adapter=adapter,
                temp_file_manager=TempFileManager(temp_dir),
            )["request_preview"]
    finally:
        rmtree(temp_dir, ignore_errors=True)

    assert preview["method"] == "POST"
    assert (
        preview["url"]
        == "https://example.com/v1beta/models/gemini-3-pro-image-preview-4k:generateContent"
    )
    assert preview["headers"]["authorization"] == "Bearer <redacted>"
    assert preview["body"]["generationConfig"]["responseModalities"] == ["TEXT", "IMAGE"]
