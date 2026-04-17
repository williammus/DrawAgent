from fastapi.testclient import TestClient

from app.main import app


def test_healthz_returns_ok() -> None:
    with TestClient(app) as client:
        response = client.get("/healthz")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["service"] == "drawagent-backend"
        assert "request_id" in payload
        assert hasattr(client.app.state, "session_store")
        assert hasattr(client.app.state, "temp_file_manager")
        assert hasattr(client.app.state, "cleanup_service")
        assert hasattr(client.app.state, "prompt_registry")
        assert hasattr(client.app.state, "prompt_renderer")
        assert hasattr(client.app.state, "style_knowledge_provider")
        assert hasattr(client.app.state, "agent_runtime")
        assert hasattr(client.app.state, "workflow_checkpoint_store")
        assert hasattr(client.app.state, "workflow_event_store")
        assert hasattr(client.app.state, "workflow_app")
        assert hasattr(client.app.state, "workflow_runner")
        assert hasattr(client.app.state, "session_task_manager")
        assert hasattr(client.app.state, "image_adapter")
        assert hasattr(client.app.state, "session_service")
        assert hasattr(client.app.state, "chat_service")
        assert hasattr(client.app.state, "generation_service")
