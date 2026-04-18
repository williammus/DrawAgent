from __future__ import annotations

import base64
from pathlib import Path
from shutil import rmtree
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import httpx
import pytest

from app.core.errors import AdapterInvocationError
from app.core.settings import Settings
from app.image import MockImageAdapter, OpenAICompatibleImageAdapter, build_image_adapter
from app.storage import TempFileManager


TEST_TEMP_ROOT = Path(__file__).resolve().parents[1] / ".test_tmp"
TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)


def make_temp_dir(name: str) -> Path:
    path = TEST_TEMP_ROOT / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


class FakeImagesClient:
    def __init__(self, response) -> None:
        self._response = response

    def generate(self, **kwargs):
        return self._response


class FakeOpenAIClient:
    def __init__(self, response) -> None:
        self.images = FakeImagesClient(response)


class FakeUrlResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return self.payload

    def __enter__(self) -> "FakeUrlResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def make_google_transport_client(
    response_json: dict,
    *,
    captured: dict | None = None,
    status_code: int = 200,
) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.update(
                {
                    "method": request.method,
                    "url": str(request.url),
                    "headers": dict(request.headers),
                    "body": request.content.decode("utf-8"),
                }
            )
        return httpx.Response(status_code, json=response_json, request=request)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_mock_image_adapter_writes_placeholder_png() -> None:
    temp_dir = make_temp_dir("mock-image")
    try:
        adapter = MockImageAdapter(TempFileManager(temp_dir))
        relative_path, meta = adapter.generate("session-1", "Draw a scientific diagram.")
        output_path = temp_dir / relative_path

        assert output_path.exists()
        assert meta.provider == "mock"
        assert meta.media_type == "image/png"
        assert output_path.read_bytes()
    finally:
        rmtree(temp_dir, ignore_errors=True)


def test_openai_compatible_image_adapter_reads_b64_payload() -> None:
    temp_dir = make_temp_dir("openai-image")
    try:
        payload = b"fake-image-payload"
        response = SimpleNamespace(
            data=[SimpleNamespace(b64_json=base64.b64encode(payload).decode("ascii"))]
        )
        adapter = OpenAICompatibleImageAdapter(
            api_key="key",
            base_url="https://example.com/v1",
            model="qwen-image",
            timeout_seconds=30,
            temp_file_manager=TempFileManager(temp_dir),
            client=FakeOpenAIClient(response),
        )

        relative_path, meta = adapter.generate("session-2", "Generate a clean paper figure.")
        output_path = temp_dir / relative_path

        assert output_path.read_bytes() == payload
        assert meta.provider == "nano-banana2"
        assert meta.relative_path == relative_path
    finally:
        rmtree(temp_dir, ignore_errors=True)


def test_openai_compatible_image_adapter_reads_url_payload() -> None:
    temp_dir = make_temp_dir("url-image")
    try:
        payload = b"fake-image-from-url"
        response = SimpleNamespace(data=[SimpleNamespace(url="https://example.com/fake.png")])
        adapter = OpenAICompatibleImageAdapter(
            api_key="key",
            base_url="https://example.com/v1",
            model="qwen-image",
            timeout_seconds=30,
            temp_file_manager=TempFileManager(temp_dir),
            client=FakeOpenAIClient(response),
        )

        with patch("app.image.adapters.urlopen", return_value=FakeUrlResponse(payload)):
            relative_path, meta = adapter.generate("session-3", "Generate a clean paper figure.")

        output_path = temp_dir / relative_path
        assert output_path.read_bytes() == payload
        assert meta.provider == "nano-banana2"
    finally:
        rmtree(temp_dir, ignore_errors=True)


def test_openai_compatible_image_adapter_builds_openai_request_preview() -> None:
    temp_dir = make_temp_dir("openai-request-preview")
    try:
        adapter = OpenAICompatibleImageAdapter(
            api_key="super-secret",
            base_url="https://example.com/v1",
            model="qwen-image",
            timeout_seconds=30,
            temp_file_manager=TempFileManager(temp_dir),
        )

        preview = adapter.build_request_preview("Generate a clean paper figure.")

        assert preview["method"] == "POST"
        assert preview["url"] == "https://example.com/v1/images/generations"
        assert preview["headers"]["authorization"] == "Bearer <redacted>"
        assert preview["body"] == {
            "prompt": "Generate a clean paper figure.",
            "model": "qwen-image",
            "response_format": "b64_json",
        }
    finally:
        rmtree(temp_dir, ignore_errors=True)


def test_openai_compatible_image_adapter_builds_google_request_preview_for_gemini_model() -> None:
    temp_dir = make_temp_dir("google-request-preview")
    try:
        adapter = OpenAICompatibleImageAdapter(
            api_key="super-secret",
            base_url="https://example.com/v1",
            model="gemini-3-pro-image-preview-4k",
            timeout_seconds=30,
            temp_file_manager=TempFileManager(temp_dir),
        )

        preview = adapter.build_request_preview("Generate a clean paper figure.")

        assert preview["method"] == "POST"
        assert (
            preview["url"]
            == "https://example.com/v1beta/models/gemini-3-pro-image-preview-4k:generateContent"
        )
        assert preview["headers"]["authorization"] == "Bearer <redacted>"
        assert preview["body"] == {
            "contents": [
                {
                    "parts": [
                        {
                            "text": "Generate a clean paper figure.",
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
            },
        }
    finally:
        rmtree(temp_dir, ignore_errors=True)


def test_openai_compatible_image_adapter_reads_google_native_payload() -> None:
    temp_dir = make_temp_dir("google-native-image")
    payload = base64.b64encode(b"fake-google-image-payload").decode("ascii")
    captured: dict = {}
    mock_client = make_google_transport_client(
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Generated image"},
                            {
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": payload,
                                }
                            },
                        ]
                    }
                }
            ]
        },
        captured=captured,
    )
    try:
        adapter = OpenAICompatibleImageAdapter(
            api_key="key",
            base_url="https://example.com/v1",
            model="gemini-3-pro-image-preview-4k",
            timeout_seconds=30,
            temp_file_manager=TempFileManager(temp_dir),
        )

        with patch("httpx.Client", return_value=mock_client):
            relative_path, meta = adapter.generate("session-google", "Generate a clean paper figure.")

        output_path = temp_dir / relative_path
        assert output_path.read_bytes() == b"fake-google-image-payload"
        assert meta.provider == "nano-banana2"
        assert (
            captured["url"]
            == "https://example.com/v1beta/models/gemini-3-pro-image-preview-4k:generateContent"
        )
        assert '"responseModalities":["TEXT","IMAGE"]' in captured["body"]
    finally:
        mock_client.close()
        rmtree(temp_dir, ignore_errors=True)


def test_openai_compatible_image_adapter_rejects_google_response_without_image_payload() -> None:
    temp_dir = make_temp_dir("google-native-missing-image")
    mock_client = make_google_transport_client(
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Only text was returned."},
                        ]
                    }
                }
            ]
        }
    )
    try:
        adapter = OpenAICompatibleImageAdapter(
            api_key="key",
            base_url="https://example.com/v1",
            model="gemini-3-pro-image-preview-4k",
            timeout_seconds=30,
            temp_file_manager=TempFileManager(temp_dir),
        )

        with patch("httpx.Client", return_value=mock_client):
            with pytest.raises(AdapterInvocationError) as exc_info:
                adapter.generate("session-google-fail", "Generate a clean paper figure.")

        assert exc_info.value.details["request_format"] == "google_generate_content"
        assert "response_excerpt" in exc_info.value.details
    finally:
        mock_client.close()
        rmtree(temp_dir, ignore_errors=True)


def test_openai_compatible_image_adapter_normalizes_google_base_url() -> None:
    temp_dir = make_temp_dir("google-base-url")
    try:
        adapter = OpenAICompatibleImageAdapter(
            api_key="key",
            base_url="https://example.com/proxy/v1/openai",
            model="gemini-3-pro-image-preview-4k",
            timeout_seconds=30,
            temp_file_manager=TempFileManager(temp_dir),
        )

        assert (
            adapter._google_generate_content_url()
            == "https://example.com/proxy/v1beta/models/gemini-3-pro-image-preview-4k:generateContent"
        )
    finally:
        rmtree(temp_dir, ignore_errors=True)


def test_openai_compatible_image_adapter_requires_complete_configuration() -> None:
    temp_dir = make_temp_dir("invalid-config")
    try:
        adapter = OpenAICompatibleImageAdapter(
            api_key="",
            base_url="",
            model="",
            timeout_seconds=30,
            temp_file_manager=TempFileManager(temp_dir),
        )

        with pytest.raises(AdapterInvocationError) as exc_info:
            adapter.generate("session-4", "Generate a clean paper figure.")

        assert exc_info.value.details == {
            "provider": "nano-banana2",
            "model": None,
            "missing_fields": ["IMAGE_API_KEY", "IMAGE_BASE_URL", "IMAGE_MODEL"],
        }
    finally:
        rmtree(temp_dir, ignore_errors=True)


def test_build_image_adapter_supports_nano_banana2_alias() -> None:
    temp_dir = make_temp_dir("provider-alias")
    try:
        settings = Settings(
            image_provider="nano_banana2",
            image_api_key="key",
            image_base_url="https://example.com/v1",
            image_model="gemini-3-pro-image-preview-4k",
            _env_file=None,
        )

        adapter = build_image_adapter(settings, temp_file_manager=TempFileManager(temp_dir))

        assert isinstance(adapter, OpenAICompatibleImageAdapter)
        assert adapter.provider_name == "nano-banana2"
        assert adapter.model == "gemini-3-pro-image-preview-4k"
    finally:
        rmtree(temp_dir, ignore_errors=True)
