from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.core.settings import Settings


TEST_TEMP_ROOT = Path(__file__).resolve().parents[1] / ".test_tmp"
TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)


def write_env_file(content: str) -> Path:
    env_path = TEST_TEMP_ROOT / f"settings-{uuid4().hex}.env"
    env_path.write_text(content, encoding="utf-8")
    return env_path


def test_settings_uses_defaults_without_env_file(monkeypatch) -> None:
    monkeypatch.delenv("IMAGE_PROVIDER", raising=False)
    settings = Settings(_env_file=None)

    assert settings.image_provider == "mock"
    assert settings.image_model == "gemini-3-pro-image-preview-4k"


def test_settings_reads_values_from_env_file(monkeypatch) -> None:
    monkeypatch.delenv("IMAGE_PROVIDER", raising=False)
    env_path = write_env_file("IMAGE_PROVIDER=nano_banana2\nIMAGE_MODEL=demo-model\n")

    settings = Settings(_env_file=env_path)

    assert settings.image_provider == "nano_banana2"
    assert settings.image_model == "demo-model"


def test_environment_variables_override_env_file(monkeypatch) -> None:
    env_path = write_env_file("IMAGE_PROVIDER=mock\nIMAGE_MODEL=file-model\n")
    monkeypatch.setenv("IMAGE_PROVIDER", "nano_banana2")
    monkeypatch.setenv("IMAGE_MODEL", "env-model")

    settings = Settings(_env_file=env_path)

    assert settings.image_provider == "nano_banana2"
    assert settings.image_model == "env-model"
