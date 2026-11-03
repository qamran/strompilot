"""Tests for the API health endpoint."""

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from strompilot.main import app


def test_health_returns_ok_with_contract_version() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "strompilot-api"
    assert payload["contract_version"] == "0.11.0"


def test_browser_origin_gets_cors_headers_foreign_origin_does_not() -> None:
    """The local Leitstand may read the API; foreign sites may not."""
    client = TestClient(app)
    allowed = client.get("/health", headers={"Origin": "http://127.0.0.1:3100"})
    assert allowed.headers.get("access-control-allow-origin") == (
        "http://127.0.0.1:3100"
    )
    foreign = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in foreign.headers


def test_startup_prepares_databases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Entering the app creates every table once, before any request."""
    memory_db = tmp_path / "memory.db"
    threads_db = tmp_path / "threads.db"
    monkeypatch.setenv("MEMORY_DB", str(memory_db))
    monkeypatch.setenv("THREADS_DB", str(threads_db))
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
    with sqlite3.connect(memory_db) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert {
        "preferences",
        "episodes",
        "meter_readings",
        "alerts",
        "auth_tokens",
        "auth_sessions",
    } <= tables
    with sqlite3.connect(threads_db) as conn:
        thread_tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert {"runs", "run_errors"} <= thread_tables
