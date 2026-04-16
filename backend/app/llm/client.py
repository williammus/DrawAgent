from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from app.core.errors import ArtifactValidationError, LLMInvocationError
from app.core.settings import Settings


class LLMClient:
    def __init__(
        self,
        *,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
        timeout_seconds: int = 120,
        max_retries: int = 2,
        client: Any | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(1, max_retries)
        self._client = client

    @classmethod
    def from_settings(cls, settings: Settings, *, client: Any | None = None) -> "LLMClient":
        return cls(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
            client=client,
        )

    def _build_client(self) -> Any:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMInvocationError(
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

    def generate_text(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> str:
        resolved_model = model or self.model
        if not resolved_model:
            raise LLMInvocationError("LLM model is not configured.", details={"model": resolved_model})

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._get_client().chat.completions.create(
                    model=resolved_model,
                    messages=messages,
                    temperature=temperature,
                )
                content = self._extract_content(response)
                if not content.strip():
                    raise LLMInvocationError(
                        "LLM returned empty content.",
                        details={"model": resolved_model, "attempt": attempt},
                    )
                return content
            except LLMInvocationError:
                raise
            except Exception as exc:
                last_error = exc

        raise LLMInvocationError(
            "LLM invocation failed after retries.",
            details={
                "model": resolved_model,
                "attempts": self.max_retries,
                "error": str(last_error) if last_error else None,
            },
        ) from last_error

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def generate_json(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        raw_text = self.generate_text(
            prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
        )
        json_candidate = self._extract_json_candidate(raw_text)
        try:
            parsed = json.loads(json_candidate)
        except json.JSONDecodeError as exc:
            raise ArtifactValidationError(
                "LLM returned invalid JSON.",
                details={"raw_response": raw_text, "json_candidate": json_candidate},
            ) from exc

        if not isinstance(parsed, Mapping):
            raise ArtifactValidationError(
                "LLM returned JSON but not an object.",
                details={"raw_response": raw_text, "parsed_type": type(parsed).__name__},
            )

        return dict(parsed)

    def _extract_content(self, response: Any) -> str:
        choices = getattr(response, "choices", None)
        if not choices:
            return ""

        message = getattr(choices[0], "message", None)
        if message is None:
            return ""

        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    maybe_text = item.get("text")
                    if maybe_text:
                        parts.append(str(maybe_text))
                else:
                    maybe_text = getattr(item, "text", None)
                    if maybe_text:
                        parts.append(str(maybe_text))
            return "\n".join(parts)

        return str(content or "")

    def _extract_json_candidate(self, text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = self._strip_code_fence(stripped)

        if stripped.startswith("{") and stripped.endswith("}"):
            return stripped

        json_block = self._find_balanced_json_block(stripped)
        if json_block is None:
            raise ArtifactValidationError(
                "No JSON object found in LLM response.",
                details={"raw_response": text},
            )

        return json_block

    def _strip_code_fence(self, text: str) -> str:
        lines = text.splitlines()
        if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
            return "\n".join(lines[1:-1]).strip()
        return text

    def _find_balanced_json_block(self, text: str) -> str | None:
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]

        return None
