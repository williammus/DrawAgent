from __future__ import annotations

import base64
from typing import Any, Protocol
from urllib.request import urlopen
from uuid import uuid4

from app.core.errors import AdapterInvocationError, InputValidationError
from app.core.settings import Settings
from app.schemas.artifacts import GeneratedImageMeta
from app.storage import TempFileManager


class BaseImageAdapter(Protocol):
    provider_name: str

    def generate(self, session_id: str, prompt_text: str) -> tuple[str, GeneratedImageMeta]:
        ...


class MockImageAdapter:
    provider_name = "mock"
    _PNG_BYTES = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8Xw8AAoMBgQf6D2sAAAAASUVORK5CYII="
    )

    def __init__(self, temp_file_manager: TempFileManager) -> None:
        self.temp_file_manager = temp_file_manager

    def generate(self, session_id: str, prompt_text: str) -> tuple[str, GeneratedImageMeta]:
        if not prompt_text.strip():
            raise InputValidationError("Prompt text is required for image generation.")

        file_name = f"generated-{uuid4().hex}.png"
        output_path = self.temp_file_manager.build_output_path(session_id, file_name)
        output_path.write_bytes(self._PNG_BYTES)
        relative_path = self.temp_file_manager.relative_path(output_path)
        return relative_path, GeneratedImageMeta(
            file_name=file_name,
            media_type="image/png",
            size_bytes=output_path.stat().st_size,
            relative_path=relative_path,
            provider=self.provider_name,
        )


class OpenAICompatibleImageAdapter:
    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: int,
        temp_file_manager: TempFileManager,
        client: Any | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.temp_file_manager = temp_file_manager
        self._client = client

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        temp_file_manager: TempFileManager,
        client: Any | None = None,
    ) -> "OpenAICompatibleImageAdapter":
        return cls(
            api_key=settings.image_api_key,
            base_url=settings.image_base_url,
            model=settings.image_model,
            timeout_seconds=settings.image_timeout_seconds,
            temp_file_manager=temp_file_manager,
            client=client,
        )

    def generate(self, session_id: str, prompt_text: str) -> tuple[str, GeneratedImageMeta]:
        if not prompt_text.strip():
            raise InputValidationError("Prompt text is required for image generation.")
        if not self.model:
            raise AdapterInvocationError("Image model is not configured.", details={"provider": self.provider_name})

        response = self._generate_image(prompt_text)
        binary_payload = self._extract_image_bytes(response)
        file_name = f"generated-{uuid4().hex}.png"
        output_path = self.temp_file_manager.build_output_path(session_id, file_name)
        output_path.write_bytes(binary_payload)
        relative_path = self.temp_file_manager.relative_path(output_path)
        return relative_path, GeneratedImageMeta(
            file_name=file_name,
            media_type="image/png",
            size_bytes=output_path.stat().st_size,
            relative_path=relative_path,
            provider=self.provider_name,
        )

    def _generate_image(self, prompt_text: str) -> Any:
        try:
            client = self._get_client()
            return client.images.generate(
                model=self.model,
                prompt=prompt_text,
                response_format="b64_json",
            )
        except TypeError:
            return self._get_client().images.generate(model=self.model, prompt=prompt_text)
        except Exception as exc:
            raise AdapterInvocationError(
                "Image adapter invocation failed.",
                details={"provider": self.provider_name, "model": self.model, "error": str(exc)},
            ) from exc

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def _build_client(self) -> Any:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise AdapterInvocationError(
                "openai package is not installed.",
                details={"dependency": "openai"},
            ) from exc

        client_kwargs: dict[str, Any] = {
            "api_key": self.api_key,
            "timeout": self.timeout_seconds,
        }
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        return OpenAI(**client_kwargs)

    def _extract_image_bytes(self, response: Any) -> bytes:
        data_items = getattr(response, "data", None) or []
        if not data_items:
            raise AdapterInvocationError(
                "Image adapter returned no data.",
                details={"provider": self.provider_name, "model": self.model},
            )

        first_item = data_items[0]
        b64_json = self._extract_field(first_item, "b64_json")
        if b64_json:
            try:
                return base64.b64decode(b64_json)
            except Exception as exc:
                raise AdapterInvocationError(
                    "Image adapter returned invalid base64 payload.",
                    details={"provider": self.provider_name, "model": self.model},
                ) from exc

        image_url = self._extract_field(first_item, "url")
        if image_url:
            try:
                with urlopen(image_url, timeout=self.timeout_seconds) as response_stream:
                    return response_stream.read()
            except Exception as exc:
                raise AdapterInvocationError(
                    "Image adapter returned an unreadable image URL.",
                    details={"provider": self.provider_name, "model": self.model, "url": image_url},
                ) from exc

        raise AdapterInvocationError(
            "Image adapter returned no supported image payload.",
            details={"provider": self.provider_name, "model": self.model},
        )

    def _extract_field(self, item: Any, field_name: str) -> str | None:
        if isinstance(item, dict):
            value = item.get(field_name)
        else:
            value = getattr(item, field_name, None)
        if value is None:
            return None
        return str(value)


def build_image_adapter(
    settings: Settings,
    *,
    temp_file_manager: TempFileManager,
    client: Any | None = None,
) -> BaseImageAdapter:
    provider = settings.image_provider.strip().lower()
    if provider in {"", "mock"}:
        return MockImageAdapter(temp_file_manager)
    if provider in {"openai", "openai_compatible"}:
        return OpenAICompatibleImageAdapter.from_settings(
            settings,
            temp_file_manager=temp_file_manager,
            client=client,
        )
    raise InputValidationError(
        "Unsupported image provider configured.",
        details={"image_provider": settings.image_provider},
    )
