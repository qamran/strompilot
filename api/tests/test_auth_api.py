"""Tests for the auth HTTP API: magic links, sessions, migration."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from strompilot.auth.store import AuthStore
from strompilot.flexalarm.store import AlertStore
from strompilot.main import SESSION_COOKIE, app
from strompilot.memory.store import MemoryStore
from strompilot.metervision.store import MeterStore

from .auth_helpers import sign_in


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Build one test client on an isolated database."""
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    return TestClient(app)


def test_request_link_returns_dev_link_in_log_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requesting a link in log mode answers sent plus a dev link."""
    monkeypatch.delenv("STROMPILOT_MAILER", raising=False)
    client = _client(tmp_path, monkeypatch)
    res = client.post("/auth/request-link", json={"email": "lena@example.de"})
    assert res.status_code == 200
    body = res.json()
    assert body["email"] == "lena@example.de"
    assert body["sent"] is True
    assert "/auth/verify?token=" in body["dev_link"]


def test_request_link_rejects_invalid_email(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An address without an @ never gets a link."""
    client = _client(tmp_path, monkeypatch)
    res = client.post("/auth/request-link", json={"email": "not-an-email"})
    assert res.status_code == 422


def test_verify_sets_session_cookie_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifying consumes the link, sets the cookie, and rejects reuse."""
    client = _client(tmp_path, monkeypatch)
    link = client.post("/auth/request-link", json={"email": "lena@example.de"}).json()[
        "dev_link"
    ]
    token = link.split("token=")[1]
    first = client.get(f"/auth/verify?token={token}")
    assert first.status_code == 200
    assert first.json()["email"] == "lena@example.de"
    assert first.json()["household_id"] == AuthStore.household_for_email(
        "lena@example.de"
    )
    assert SESSION_COOKIE in first.cookies
    second = client.get(f"/auth/verify?token={token}")
    assert second.status_code == 401
    unknown = client.get("/auth/verify?token=never-issued")
    assert unknown.status_code == 401


def test_me_needs_a_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """/auth/me answers the signed-in household and 401s the anonymous."""
    client = _client(tmp_path, monkeypatch)
    assert client.get("/auth/me").status_code == 401
    sign_in(client, "h1", email="lena@example.de")
    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "lena@example.de"
    assert me.json()["household_id"] == "h1"


def test_sign_out_revokes_the_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Signing out revokes the session and clears the cookie."""
    client = _client(tmp_path, monkeypatch)
    sign_in(client, "h1")
    out = client.post("/auth/sign-out")
    assert out.status_code == 200
    assert out.json()["signed_out"] is True
    assert client.get("/auth/me").status_code == 401


def test_household_endpoints_enforce_the_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Household data needs a session and refuses foreign households."""
    client = _client(tmp_path, monkeypatch)
    assert client.get("/memory/preferences?household_id=h1").status_code == 401
    sign_in(client, "h1")
    match = client.get("/memory/preferences?household_id=h1")
    assert match.status_code == 200
    foreign = client.get("/memory/preferences?household_id=h2")
    assert foreign.status_code == 403


def test_migrate_copies_a_local_profile_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Migration copies prefs, episodes, readings, and alerts exactly once."""
    client = _client(tmp_path, monkeypatch)
    db = tmp_path / "memory.db"
    memory = MemoryStore(db)
    memory.set_preference("demo-haushalt", "devices", ["E-Auto"])
    memory.add_episode("demo-haushalt", "plan", "erster Plan")
    MeterStore(db).propose(
        "demo-haushalt", 4217.3, datetime.now(UTC), "high", None, "photo.png"
    )
    AlertStore(db).record(
        "demo-haushalt",
        "demo-haushalt:2026-11-02:cheap:02:00-04:00",
        "cheap",
        "Cheap hour",
        "body",
        "new",
        None,
        "r",
    )
    sign_in(client, "hh_new", email="lena@example.de")
    moved = client.post("/auth/migrate", json={"from_household": "demo-haushalt"})
    assert moved.status_code == 200
    assert moved.json()["migrated"]["preferences"] == 1
    prefs = client.get("/memory/preferences?household_id=hh_new").json()
    assert prefs["preferences"] == {"devices": ["E-Auto"]}
    history = client.get("/memory/history?household_id=hh_new").json()
    assert [e["text"] for e in history["episodes"]] == ["erster Plan"]
    readings = client.get("/meter/readings?household_id=hh_new").json()
    assert len(readings["readings"]) == 1
    alerts = client.get("/flexalarm/alerts?household_id=hh_new").json()
    assert len(alerts["alerts"]) == 1
    again = client.post("/auth/migrate", json={"from_household": "demo-haushalt"})
    assert again.status_code == 409


def test_migrate_refuses_an_empty_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Migrating from an unknown household answers 404."""
    client = _client(tmp_path, monkeypatch)
    sign_in(client, "hh_new")
    res = client.post("/auth/migrate", json={"from_household": "nobody"})
    assert res.status_code == 404
