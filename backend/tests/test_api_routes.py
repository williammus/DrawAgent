from __future__ import annotations

import json
import time
from copy import deepcopy

from fastapi.testclient import TestClient

from app.image import MockImageAdapter
from app.main import app
from app.schemas import TextArtifact
from app.schemas.events import StageCompletedEvent, StageStartedEvent
from app.schemas.common import StageName


class StubChatService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def run_workflow(
        self,
        *,
        session_id: str,
        request_id: str,
        source_text: str | None = None,
        user_feedback: str | None = None,
    ) -> str:
        self.calls.append(
            {
                "session_id": session_id,
                "request_id": request_id,
                "source_text": source_text,
                "user_feedback": user_feedback,
            }
        )
        return "run_source_text"

    def resume_workflow(
        self,
        *,
        session_id: str,
        request_id: str,
        user_feedback: str,
    ) -> str:
        self.calls.append(
            {
                "session_id": session_id,
                "request_id": request_id,
                "user_feedback": user_feedback,
                "resume": True,
            }
        )
        return "resume_user_feedback"


def wait_until(predicate, timeout_seconds: float = 2.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def test_phase5_api_flow() -> None:
    with TestClient(app) as client:
        mock_image_adapter = MockImageAdapter(client.app.state.temp_file_manager)
        client.app.state.image_adapter = mock_image_adapter
        client.app.state.generation_service.image_adapter = mock_image_adapter

        session_response = client.post("/api/session/init")
        assert session_response.status_code == 201
        session_payload = session_response.json()
        session_id = session_payload["session_id"]

        upload_response = client.post(
            "/api/upload",
            data={"session_id": session_id},
            files=[("files", ("paper.md", b"# Abstract", "text/markdown"))],
        )
        assert upload_response.status_code == 201
        uploaded_file = upload_response.json()["files"][0]
        file_id = uploaded_file["file_id"]
        state = client.app.state.session_store.get_state(session_id)
        assert len(state["uploaded_files"]) == 1
        assert state["source_files"][0].file_id == file_id

        stub_chat_service = StubChatService()
        client.app.state.chat_service = stub_chat_service
        message_response = client.post(
            "/api/chat/run",
            json={
                "session_id": session_id,
                "source_text": "Please create a figure.",
            },
        )
        assert message_response.status_code == 202
        message_payload = message_response.json()
        assert message_payload["accepted"] is True
        assert message_payload["stream_url"] == f"/api/chat/stream/{session_id}"
        assert message_payload["operation"] == "run_source_text"
        assert stub_chat_service.calls[0]["source_text"] == "Please create a figure."

        client.app.state.workflow_event_store.append(
            session_id,
            StageStartedEvent(
                session_id=session_id,
                stage=StageName.PLANNING,
                request_id="req-stream",
                message="Planning started.",
            ),
        )
        with client.stream("GET", f"/api/chat/stream/{session_id}?once=true") as response:
            assert response.status_code == 200
            streamed_payload = None
            for line in response.iter_lines():
                if line.startswith("data: "):
                    streamed_payload = json.loads(line.removeprefix("data: "))
                    break
        assert streamed_payload is not None
        assert streamed_payload["event_type"] == "stage_started"
        assert streamed_payload["data"]["message"] == "Planning started."

        artifacts_response = client.get(f"/api/artifacts/{session_id}")
        assert artifacts_response.status_code == 200
        assert artifacts_response.json()["final_prompt_artifact"] is None

        record = client.app.state.session_store.get_session(session_id)
        new_state = deepcopy(record.state)
        new_state["artifacts"]["final_prompt_artifact"] = TextArtifact(
            tool_name="summary",
            content="A clean scientific pipeline figure.",
            prompt_version="v-test",
            metadata={"ready_for_generation": True},
        )
        client.app.state.session_store.update_state(session_id, new_state)

        artifacts_response = client.get(f"/api/artifacts/{session_id}")
        assert artifacts_response.status_code == 200
        assert "A clean scientific pipeline figure." in artifacts_response.json()["final_prompt_artifact"]["content"]

        generate_response = client.post(f"/api/generate/{session_id}")
        assert generate_response.status_code == 202
        assert generate_response.json()["status"] == "accepted"
        assert generate_response.json()["download_url"] == f"/api/download/{session_id}"

        assert wait_until(
            lambda: client.app.state.session_store.get_state(session_id)["generated_image_meta"] is not None
        )

        download_response = client.get(f"/api/download/{session_id}")
        assert download_response.status_code == 200
        assert download_response.headers["content-type"] == "image/png"
        assert download_response.content

        delete_upload_response = client.delete(f"/api/upload/{session_id}/{file_id}")
        assert delete_upload_response.status_code == 200
        assert delete_upload_response.json()["deleted"] is True
        assert client.app.state.session_store.get_state(session_id)["uploaded_files"] == []

        delete_session_response = client.delete(f"/api/session/{session_id}")
        assert delete_session_response.status_code == 200
        delete_payload = delete_session_response.json()
        assert delete_payload["deleted"] is True
        assert delete_payload["cleanup"]["removed_sessions"] == [session_id]


def test_stream_supports_after_id_replay() -> None:
    with TestClient(app) as client:
        session_response = client.post("/api/session/init")
        session_id = session_response.json()["session_id"]

        client.app.state.workflow_event_store.append(
            session_id,
            StageStartedEvent(
                session_id=session_id,
                stage=StageName.PLANNING,
                request_id="req-1",
                message="Planning started.",
            ),
        )
        client.app.state.workflow_event_store.append(
            session_id,
            StageCompletedEvent(
                session_id=session_id,
                stage=StageName.LOGIC_READY,
                request_id="req-2",
                message="Logician completed.",
            ),
        )

        streamed_payloads: list[dict[str, object]] = []
        with client.stream("GET", f"/api/chat/stream/{session_id}?once=true&after_id=1") as response:
            assert response.status_code == 200
            for line in response.iter_lines():
                if line.startswith("data: "):
                    streamed_payloads.append(json.loads(line.removeprefix("data: ")))

        assert len(streamed_payloads) == 1
        assert streamed_payloads[0]["event_id"] == 2
        assert streamed_payloads[0]["event_type"] == "stage_completed"
        assert streamed_payloads[0]["data"]["message"] == "Logician completed."


def test_resume_route_uses_explicit_resume_contract() -> None:
    with TestClient(app) as client:
        session_response = client.post("/api/session/init")
        session_id = session_response.json()["session_id"]

        stub_chat_service = StubChatService()
        client.app.state.chat_service = stub_chat_service
        response = client.post(
            "/api/chat/resume",
            json={
                "session_id": session_id,
                "user_feedback": "补充摘要内容",
            },
        )

        assert response.status_code == 202
        payload = response.json()
        assert payload["operation"] == "resume_user_feedback"
        assert stub_chat_service.calls[0]["resume"] is True
        assert stub_chat_service.calls[0]["user_feedback"] == "补充摘要内容"
