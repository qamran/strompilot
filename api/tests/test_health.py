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
    assert payload["contract_version"] == "0.7.0"
