from types import SimpleNamespace

import pytest

from app.core.errors import LLMInvocationError
from app.llm import LLMClient


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


def make_response(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def test_generate_json_accepts_fenced_payload() -> None:
    client = LLMClient(
        model="test-model",
        client=FakeOpenAIClient([make_response("```json\n{\"ok\": true}\n```")]),
    )

    payload = client.generate_json("Return JSON")

    assert payload == {"ok": True}


def test_generate_text_retries_until_success() -> None:
    client = LLMClient(
        model="test-model",
        max_retries=2,
        client=FakeOpenAIClient([RuntimeError("temporary"), make_response("{\"ok\": true}")]),
    )

    text = client.generate_text("Return JSON")

    assert "{\"ok\": true}" in text


def test_generate_text_wraps_final_failure() -> None:
    client = LLMClient(
        model="test-model",
        base_url="https://example.com/v1",
        max_retries=2,
        client=FakeOpenAIClient([RuntimeError("bad"), RuntimeError("still bad")]),
    )

    with pytest.raises(LLMInvocationError) as exc_info:
        client.generate_text("Return JSON")

    assert exc_info.value.details["base_url"] == "https://example.com/v1"
    assert exc_info.value.details["error"] == "still bad"


def test_run_connectivity_diagnostic_reports_success() -> None:
    client = LLMClient(
        model="test-model",
        base_url="https://example.com/v1",
        client=FakeOpenAIClient([make_response('{"ok": true, "ping": "pong"}')]),
    )

    payload = client.run_connectivity_diagnostic()

    assert payload["ok"] is True
    assert payload["model"] == "test-model"
    assert payload["base_url"] == "https://example.com/v1"
