"""Tests for the API health endpoint."""

from fastapi.testclient import TestClient

from strompilot.main import app


def test_health_returns_ok_with_contract_version() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "strompilot-api"
    assert payload["contract_version"] == "0.9.0"


def test_browser_origin_gets_cors_headers_foreign_origin_does_not() -> None:
    """The local Leitstand may read the API; foreign sites may not."""
    client = TestClient(app)
    allowed = client.get("/health", headers={"Origin": "http://127.0.0.1:3100"})
    assert allowed.headers.get("access-control-allow-origin") == (
        "http://127.0.0.1:3100"
    )
    foreign = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in foreign.headers
