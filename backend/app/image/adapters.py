from __future__ import annotations

import base64
import json
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit
from urllib.request import urlopen
from uuid import uuid4

from app.core.errors import AdapterInvocationError, InputValidationError
from app.core.settings import Settings
from app.schemas.artifacts import GeneratedImageMeta
from app.storage.temp_files import TempFileManager


MOCK_IMAGE_PROVIDER = "mock"
NANO_BANANA2_PROVIDER = "nano-banana2"
GOOGLE_GENERATE_CONTENT_FORMAT = "google_generate_content"
OPENAI_IMAGES_GENERATE_FORMAT = "openai_images_generate"


class BaseImageAdapter(Protocol):
    provider_name: str

    def generate(self, session_id: str, prompt_text: str) -> tuple[str, GeneratedImageMeta]:
        ...


class MockImageAdapter:
    provider_name = MOCK_IMAGE_PROVIDER
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
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: int,
        temp_file_manager: TempFileManager,
        provider_name: str = NANO_BANANA2_PROVIDER,
        client: Any | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.temp_file_manager = temp_file_manager
        self.provider_name = provider_name
        self._client = client

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        temp_file_manager: TempFileManager,
        provider_name: str = NANO_BANANA2_PROVIDER,
        client: Any | None = None,
    ) -> "OpenAICompatibleImageAdapter":
        return cls(
            api_key=settings.image_api_key,
            base_url=settings.image_base_url,
            model=settings.image_model,
            timeout_seconds=settings.image_timeout_seconds,
            temp_file_manager=temp_file_manager,
            provider_name=provider_name,
            client=client,
        )

    def generate(self, session_id: str, prompt_text: str) -> tuple[str, GeneratedImageMeta]:
        if not prompt_text.strip():
            raise InputValidationError("Prompt text is required for image generation.")
        self._validate_configuration()

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

    def _validate_configuration(self) -> None:
        missing_fields: list[str] = []
        if not self.api_key.strip():
            missing_fields.append("IMAGE_API_KEY")
        if not self.base_url.strip():
            missing_fields.append("IMAGE_BASE_URL")
        if not self.model.strip():
            missing_fields.append("IMAGE_MODEL")

        if missing_fields:
            raise AdapterInvocationError(
                "Image adapter is not fully configured.",
                details={
                    "provider": self.provider_name,
                    "model": self.model or None,
                    "missing_fields": missing_fields,
                },
            )

    def _generate_image(self, prompt_text: str) -> Any:
        if self._uses_google_generate_content():
            return self._generate_google_native_image(prompt_text)

        try:
            client = self._get_client()
            try:
                return client.images.generate(
                    model=self.model,
                    prompt=prompt_text,
                    response_format="b64_json",
                )
            except TypeError:
                return client.images.generate(model=self.model, prompt=prompt_text)
        except Exception as exc:
            raise self._build_invocation_error(str(exc)) from exc

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def _build_client(self, *, http_client: Any | None = None) -> Any:
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
        if http_client is not None:
            client_kwargs["http_client"] = http_client
        return OpenAI(**client_kwargs)

    def build_request_preview(self, prompt_text: str) -> dict[str, Any]:
        self._validate_configuration()
        if self._uses_google_generate_content():
            return self._build_google_request_preview(prompt_text)

        try:
            import httpx
        except ImportError as exc:
            raise AdapterInvocationError(
                "httpx package is not installed.",
                details={"dependency": "httpx"},
            ) from exc

        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            headers = dict(request.headers)
            if "authorization" in headers:
                headers["authorization"] = "Bearer <redacted>"
            try:
                body: Any = json.loads(request.content.decode("utf-8"))
            except json.JSONDecodeError:
                body = request.content.decode("utf-8", errors="replace")

            captured.update(
                {
                    "method": request.method,
                    "url": str(request.url),
                    "headers": headers,
                    "body": body,
                }
            )
            return httpx.Response(
                200,
                json={
                    "created": 0,
                    "data": [
                        {
                            "b64_json": base64.b64encode(MockImageAdapter._PNG_BYTES).decode("ascii"),
                        }
                    ],
                },
                request=request,
            )

        http_client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            preview_client = self._build_client(http_client=http_client)
            try:
                preview_client.images.generate(
                    model=self.model,
                    prompt=prompt_text,
                    response_format="b64_json",
                )
            except TypeError:
                preview_client.images.generate(model=self.model, prompt=prompt_text)
        finally:
            http_client.close()

        return captured

    def _extract_image_bytes(self, response: Any) -> bytes:
        if self._uses_google_generate_content():
            return self._extract_google_image_bytes(response)

        data_items = getattr(response, "data", None) or []
        if not data_items:
            raise AdapterInvocationError(
                "Image adapter returned no data.",
                details=self._build_error_details(),
            )

        first_item = data_items[0]
        b64_json = self._extract_field(first_item, "b64_json")
        if b64_json:
            try:
                return base64.b64decode(b64_json)
            except Exception as exc:
                raise AdapterInvocationError(
                    "Image adapter returned invalid base64 payload.",
                    details=self._build_error_details(),
                ) from exc

        image_url = self._extract_field(first_item, "url")
        if image_url:
            try:
                with urlopen(image_url, timeout=self.timeout_seconds) as response_stream:
                    return response_stream.read()
            except Exception as exc:
                raise AdapterInvocationError(
                    "Image adapter returned an unreadable image URL.",
                    details={
                        **self._build_error_details(),
                        "url": image_url,
                    },
                ) from exc

        raise AdapterInvocationError(
            "Image adapter returned no supported image payload.",
            details=self._build_error_details(),
        )

    def _extract_field(self, item: Any, field_name: str) -> str | None:
        if isinstance(item, dict):
            value = item.get(field_name)
        else:
            value = getattr(item, field_name, None)
        if value is None:
            return None
        return str(value)

    def _uses_google_generate_content(self) -> bool:
        return self.model.strip().lower().startswith("gemini-")

    def _request_format(self) -> str:
        if self._uses_google_generate_content():
            return GOOGLE_GENERATE_CONTENT_FORMAT
        return OPENAI_IMAGES_GENERATE_FORMAT

    def _build_error_details(self, *, error: str | None = None) -> dict[str, Any]:
        details: dict[str, Any] = {
            "provider": self.provider_name,
            "model": self.model,
            "request_format": self._request_format(),
        }
        if error is not None:
            details["error"] = error
        return details

    def _build_invocation_error(self, error: str) -> AdapterInvocationError:
        return AdapterInvocationError(
            "Image adapter invocation failed.",
            details=self._build_error_details(error=error),
        )

    def _generate_google_native_image(self, prompt_text: str) -> Any:
        try:
            return self._post_google_generate_content(prompt_text)
        except AdapterInvocationError:
            raise
        except Exception as exc:
            raise self._build_invocation_error(str(exc)) from exc

    def _post_google_generate_content(
        self,
        prompt_text: str,
        *,
        http_client: Any | None = None,
    ) -> Any:
        try:
            import httpx
        except ImportError as exc:
            raise AdapterInvocationError(
                "httpx package is not installed.",
                details={"dependency": "httpx"},
            ) from exc

        own_client = http_client is None
        client = http_client or httpx.Client(timeout=self.timeout_seconds)
        try:
            response = client.post(
                self._google_generate_content_url(),
                headers=self._google_headers(),
                json=self._google_request_body(prompt_text),
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise self._build_invocation_error(
                f"Error code: {exc.response.status_code} - {self._format_http_error_payload(exc.response)}"
            ) from exc
        except httpx.HTTPError as exc:
            raise self._build_invocation_error(str(exc)) from exc
        finally:
            if own_client:
                client.close()

    def _build_google_request_preview(self, prompt_text: str) -> dict[str, Any]:
        try:
            import httpx
        except ImportError as exc:
            raise AdapterInvocationError(
                "httpx package is not installed.",
                details={"dependency": "httpx"},
            ) from exc

        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            headers = dict(request.headers)
            if "authorization" in headers:
                headers["authorization"] = "Bearer <redacted>"
            captured.update(
                {
                    "method": request.method,
                    "url": str(request.url),
                    "headers": headers,
                    "body": json.loads(request.content.decode("utf-8")),
                }
            )
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {"text": "Generated image"},
                                    {
                                        "inlineData": {
                                            "mimeType": "image/png",
                                            "data": base64.b64encode(MockImageAdapter._PNG_BYTES).decode("ascii"),
                                        }
                                    },
                                ]
                            }
                        }
                    ]
                },
                request=request,
            )

        http_client = httpx.Client(transport=httpx.MockTransport(handler), timeout=self.timeout_seconds)
        try:
            self._post_google_generate_content(prompt_text, http_client=http_client)
        finally:
            http_client.close()

        return captured

    def _google_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _google_request_body(self, prompt_text: str) -> dict[str, Any]:
        return {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt_text,
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
            },
        }

    def _google_generate_content_url(self) -> str:
        base_url = self._normalized_google_base_url()
        return f"{base_url}/v1beta/models/{self.model}:generateContent"

    def _normalized_google_base_url(self) -> str:
        parsed = urlsplit(self.base_url.strip())
        segments = [segment for segment in parsed.path.split("/") if segment]
        while segments and segments[-1].lower() in {"v1", "v1beta", "openai"}:
            segments.pop()
        normalized_path = f"/{'/'.join(segments)}" if segments else ""
        return urlunsplit((parsed.scheme, parsed.netloc, normalized_path, "", "")).rstrip("/")

    def _extract_google_image_bytes(self, response: Any) -> bytes:
        candidates = response.get("candidates") if isinstance(response, dict) else None
        if not candidates:
            raise AdapterInvocationError(
                "Image adapter returned no data.",
                details={
                    **self._build_error_details(),
                    "response_excerpt": self._summarize_response(response),
                },
            )

        for candidate in candidates:
            content = candidate.get("content") if isinstance(candidate, dict) else None
            parts = content.get("parts") if isinstance(content, dict) else None
            if not parts:
                continue
            for part in parts:
                if not isinstance(part, dict):
                    continue
                inline_data = part.get("inlineData") or part.get("inline_data")
                if not isinstance(inline_data, dict):
                    continue
                payload = inline_data.get("data")
                if not payload:
                    continue
                try:
                    return base64.b64decode(str(payload))
                except Exception as exc:
                    raise AdapterInvocationError(
                        "Image adapter returned invalid base64 payload.",
                        details={
                            **self._build_error_details(),
                            "response_excerpt": self._summarize_response(response),
                        },
                    ) from exc

        raise AdapterInvocationError(
            "Image adapter returned no supported image payload.",
            details={
                **self._build_error_details(),
                "response_excerpt": self._summarize_response(response),
            },
        )

    def _format_http_error_payload(self, response: Any) -> str:
        try:
            payload = response.json()
            return json.dumps(payload, ensure_ascii=False)
        except Exception:
            return response.text

    def _summarize_response(self, response: Any) -> str:
        try:
            payload = json.dumps(response, ensure_ascii=False)
        except TypeError:
            payload = str(response)
        if len(payload) > 400:
            return f"{payload[:397]}..."
        return payload


def build_image_adapter(
    settings: Settings,
    *,
    temp_file_manager: TempFileManager,
    client: Any | None = None,
) -> BaseImageAdapter:
    provider = settings.image_provider.strip().lower()
    if provider in {"", MOCK_IMAGE_PROVIDER}:
        return MockImageAdapter(temp_file_manager)
    if provider in {"nano_banana2", NANO_BANANA2_PROVIDER, "openai", "openai_compatible"}:
        return OpenAICompatibleImageAdapter.from_settings(
            settings,
            temp_file_manager=temp_file_manager,
            provider_name=NANO_BANANA2_PROVIDER,
            client=client,
        )
    raise InputValidationError(
        "Unsupported image provider configured.",
        details={"image_provider": settings.image_provider},
    )
