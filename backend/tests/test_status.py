import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.library import Conversation, Document


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path)), base_url="http://localhost") as active_client:
        yield active_client


def test_health(client):
    response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_dashboard_uses_database(client):
    assert client.get("/api/dashboard").json()["document_count"] == 0
    with client.app.state.engine.begin() as connection:
        connection.execute(Document.__table__.insert().values(id="1", name="Guide.pdf"))
        connection.execute(Conversation.__table__.insert().values(id="1", title="Guide"))
    result = client.get("/api/dashboard").json()
    assert result["document_count"] == result["conversation_count"] == 1
    assert result["ai"] == client.get("/api/ai/status").json()
    assert result["ai"]["status"] == "unavailable"


def test_health_reports_database_failure(client, monkeypatch):
    from sqlalchemy.exc import OperationalError

    def fail():
        raise OperationalError("SELECT 1", {}, RuntimeError("test failure"))

    monkeypatch.setattr(client.app.state.engine, "connect", fail)
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"



def test_local_hosts_and_browser_write_origins(client):
    assert client.get("/api/health", headers={"Host": "external.invalid"}).status_code == 400
    response = client.post("/api/documents/upload", headers={"Origin": "https://external.invalid"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "origin_forbidden"
    assert client.post("/api/documents/upload", headers={"Origin": "http://localhost"}).status_code == 422
    assert client.post("/api/documents/upload", headers={"Origin": "http://127.0.0.1:5173"}).status_code == 422
