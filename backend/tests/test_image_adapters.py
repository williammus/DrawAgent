from __future__ import annotations

import base64
from pathlib import Path
from shutil import rmtree
from types import SimpleNamespace
from uuid import uuid4

from app.image import MockImageAdapter, OpenAICompatibleImageAdapter
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
            model="gemini-3-pro-image-preview-4k",
            timeout_seconds=30,
            temp_file_manager=TempFileManager(temp_dir),
            client=FakeOpenAIClient(response),
        )

        relative_path, meta = adapter.generate("session-2", "Generate a clean paper figure.")
        output_path = temp_dir / relative_path

        assert output_path.read_bytes() == payload
        assert meta.provider == "openai"
        assert meta.relative_path == relative_path
    finally:
        rmtree(temp_dir, ignore_errors=True)
