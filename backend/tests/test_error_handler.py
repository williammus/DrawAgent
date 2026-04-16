from fastapi.testclient import TestClient

from app.core.errors import SessionNotFoundError
from app.main import create_app


def test_drawagent_error_returns_structured_response() -> None:
    app = create_app()

    @app.get("/test-session-error")
    async def test_session_error() -> None:
        raise SessionNotFoundError(details={"session_id": "missing-session"})

    with TestClient(app) as client:
        response = client.get("/test-session-error")

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "session_not_found"
    assert payload["error"]["details"] == {"session_id": "missing-session"}
    assert "request_id" in payload["error"]
