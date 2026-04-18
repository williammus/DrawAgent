from __future__ import annotations

import json
import time
from typing import Any
from uuid import uuid4

from app.core.errors import DrawAgentError
from app.core.settings import Settings, get_settings
from app.image.adapters import BaseImageAdapter, MockImageAdapter, build_image_adapter
from app.llm import LLMClient
from app.storage.temp_files import TempFileManager


LLM_DIAGNOSTIC_PROMPT = (
    'Return only one JSON object: {"ok": true, "ping": "pong", "channel": "llm"}.'
)
IMAGE_DIAGNOSTIC_PROMPT = "Generate a minimal scientific diagram placeholder with one title box and one arrow."


def _build_request_preview(adapter: BaseImageAdapter, prompt_text: str) -> dict[str, Any] | None:
    preview_builder = getattr(adapter, "build_request_preview", None)
    if not callable(preview_builder):
        return None

    try:
        return preview_builder(prompt_text)
    except Exception as exc:  # pragma: no cover - defensive, diagnostics should not fail on preview capture
        return {
            "ok": False,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }


def diagnose_llm(
    *,
    settings: Settings | None = None,
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    resolved_settings = settings or get_settings()
    client = llm_client or LLMClient.from_settings(resolved_settings)
    return client.run_connectivity_diagnostic()


def diagnose_image(
    *,
    settings: Settings | None = None,
    image_adapter: BaseImageAdapter | None = None,
    temp_file_manager: TempFileManager | None = None,
) -> dict[str, Any]:
    resolved_settings = settings or get_settings()
    file_manager = temp_file_manager or TempFileManager(resolved_settings.temp_dir)
    adapter = image_adapter or build_image_adapter(
        resolved_settings,
        temp_file_manager=file_manager,
    )
    provider = getattr(adapter, "provider_name", "unknown")
    model = getattr(adapter, "model", None)
    request_preview = _build_request_preview(adapter, IMAGE_DIAGNOSTIC_PROMPT)

    if isinstance(adapter, MockImageAdapter):
        return {
            "ok": True,
            "provider": provider,
            "base_url": None,
            "model": model,
            "latency_ms": 0,
            "note": "Mock image adapter is configured; no external image request was made.",
            "request_preview": request_preview,
        }

    session_id = f"diag-image-{uuid4().hex}"
    started_at = time.perf_counter()
    try:
        relative_path, meta = adapter.generate(session_id, IMAGE_DIAGNOSTIC_PROMPT)
    except Exception as exc:  # pragma: no cover - error shape depends on provider SDK
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        failure_payload = {
            "ok": False,
            "provider": provider,
            "base_url": getattr(adapter, "base_url", None),
            "model": model,
            "latency_ms": latency_ms,
            "request_preview": request_preview,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }
        if isinstance(exc, DrawAgentError):
            failure_payload["error_code"] = exc.error_code
            failure_payload["details"] = exc.details
        return failure_payload
    finally:
        file_manager.delete_session_dir(session_id)

    latency_ms = int((time.perf_counter() - started_at) * 1000)
    return {
        "ok": True,
        "provider": provider,
        "base_url": getattr(adapter, "base_url", None),
        "model": model,
        "latency_ms": latency_ms,
        "request_preview": request_preview,
        "relative_path": relative_path,
        "media_type": meta.media_type,
        "size_bytes": meta.size_bytes,
    }


def main(argv: list[str] | None = None) -> int:
    args = argv or []
    if len(args) != 1 or args[0] not in {"llm", "image"}:
        print("Usage: python -m app.diagnostics <llm|image>")
        return 1

    result = diagnose_llm() if args[0] == "llm" else diagnose_image()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
