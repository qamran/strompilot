"""Tests for the memory HTTP API."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from strompilot.auth.models import AuthError
from strompilot.auth.store import AuthStore
from strompilot.flexalarm.store import AlertStore
from strompilot.main import _art_path, app, record_run_started
from strompilot.memory.store import MemoryStore
from strompilot.metervision.store import MeterStore
from tests.test_approval_api import pause_thread

from .auth_helpers import sign_in


def test_preference_crud_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    client = TestClient(app)
    sign_in(client, "h1")
    put = client.put(
        "/memory/preferences/quiet_hours?household_id=h1",
        json={"value": {"start": "22:00"}},
    )
    assert put.status_code == 200
    assert put.json()["value"] == {"start": "22:00"}
    listed = client.get("/memory/preferences?household_id=h1")
    assert listed.status_code == 200
    assert listed.json()["preferences"] == {"quiet_hours": {"start": "22:00"}}
    deleted = client.delete("/memory/preferences/quiet_hours?household_id=h1")
    assert deleted.status_code == 200
    missing = client.delete("/memory/preferences/quiet_hours?household_id=h1")
    assert missing.status_code == 404


def test_history_add_list_and_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    client = TestClient(app)
    sign_in(client, "h1")
    first = client.post(
        "/memory/history?household_id=h1",
        json={"kind": "plan", "text": "erster Plan"},
    )
    assert first.status_code == 200
    assert first.json()["id"] >= 1
    client.post(
        "/memory/history?household_id=h1",
        json={"kind": "feedback", "text": "mag Abende"},
    )
    listed = client.get("/memory/history?household_id=h1")
    assert [episode["text"] for episode in listed.json()["episodes"]] == [
        "mag Abende",
        "erster Plan",
    ]
    plans = client.get("/memory/history?household_id=h1&kind=plan")
    assert [episode["text"] for episode in plans.json()["episodes"]] == ["erster Plan"]


def test_households_stay_isolated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    client = TestClient(app)
    sign_in(client, "h1")
    other = TestClient(app)
    sign_in(other, "h2")
    client.put("/memory/preferences/k?household_id=h1", json={"value": "a"})
    created = client.post(
        "/memory/history?household_id=h1",
        json={"kind": "note", "text": "privat"},
    )
    episode_id = created.json()["id"]
    assert other.get("/memory/preferences?household_id=h2").json()["preferences"] == {}
    assert other.get("/memory/history?household_id=h2").json()["episodes"] == []
    assert client.get("/memory/preferences?household_id=h2").status_code == 403
    assert (
        other.delete(f"/memory/history/{episode_id}?household_id=h2").status_code == 404
    )
    assert (
        client.delete(f"/memory/history/{episode_id}?household_id=h2").status_code
        == 403
    )
    assert (
        client.delete(f"/memory/history/{episode_id}?household_id=h1").status_code
        == 200
    )


def test_forget_household_wipes_everything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    client = TestClient(app)
    sign_in(client, "h1")
    other = TestClient(app)
    sign_in(other, "h2")
    client.put("/memory/preferences/k?household_id=h1", json={"value": "a"})
    client.post(
        "/memory/history?household_id=h1",
        json={"kind": "note", "text": "vergiss mich"},
    )
    other.put("/memory/preferences/k?household_id=h2", json={"value": "b"})
    forgotten = client.delete("/memory/household?household_id=h1")
    assert forgotten.status_code == 200
    assert client.get("/memory/preferences?household_id=h1").status_code == 401
    sign_in(client, "h1")
    assert client.get("/memory/preferences?household_id=h1").json()["preferences"] == {}
    assert client.get("/memory/history?household_id=h1").json()["episodes"] == []
    assert other.get("/memory/preferences?household_id=h2").json()["preferences"] == {
        "k": "b"
    }


def test_forget_household_cascades_everywhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Forgetting wipes prefs, readings, photos, alerts, art, auth, threads."""
    memory_db = tmp_path / "memory.db"
    threads_db = tmp_path / "threads.db"
    photos_dir = tmp_path / "photos"
    art_dir = tmp_path / "art"
    monkeypatch.setenv("MEMORY_DB", str(memory_db))
    monkeypatch.setenv("THREADS_DB", str(threads_db))
    monkeypatch.setenv("METER_PHOTOS_DIR", str(photos_dir))
    monkeypatch.setenv("REPORT_ART_DIR", str(art_dir))
    client = TestClient(app)
    email = "forget@example.de"
    household = AuthStore.household_for_email(email)
    sign_in(client, household, email=email)
    other = TestClient(app)
    sign_in(other, "h2", email="keep@example.de")

    MemoryStore(memory_db).set_preference(household, "k", "a")
    MemoryStore(memory_db).set_preference("h2", "k", "b")
    photos_dir.mkdir(parents=True, exist_ok=True)
    (photos_dir / "meter1.png").write_bytes(b"fake-photo")
    MeterStore(memory_db).propose(
        household_id=household,
        value_kwh=100.0,
        read_at=datetime.now(UTC),
        confidence="high",
        sam_box=None,
        photo_path="meter1.png",
        serial=None,
    )
    AlertStore(memory_db).record(
        household, "key-1", "cheap_window", "Cheap", "body", "new", None, "test"
    )
    AlertStore(memory_db).record(
        "h2", "key-2", "cheap_window", "Cheap", "body", "new", None, "test"
    )
    art = _art_path(household, "2026-10")
    art.parent.mkdir(parents=True, exist_ok=True)
    art.write_bytes(b"fake-art")
    raw_token = AuthStore(memory_db).issue_token(email)
    pause_thread(threads_db, "t-forget")
    record_run_started(threads_db, "t-forget", household)

    forgotten = client.delete(f"/memory/household?household_id={household}")
    assert forgotten.status_code == 200

    assert MemoryStore(memory_db).list_preferences(household) == []
    assert MemoryStore(memory_db).list_preferences("h2") != []
    assert MeterStore(memory_db).list_readings(household) == []
    assert not (photos_dir / "meter1.png").exists()
    assert AlertStore(memory_db).list_alerts(household) == []
    assert len(AlertStore(memory_db).list_alerts("h2")) == 1
    assert not art.exists()
    with pytest.raises(AuthError, match="invalid or expired"):
        AuthStore(memory_db).consume_token(raw_token)
    assert (
        client.get(f"/memory/preferences?household_id={household}").status_code == 401
    )
    assert other.get("/memory/preferences?household_id=h2").status_code == 200
    assert client.get("/plan/t-forget").status_code in (401, 404)


def test_blank_household_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    client = TestClient(app)
    sign_in(client, "h1")
    response = client.get("/memory/preferences?household_id=%20%20")
    assert response.status_code == 422
    created = client.post(
        "/memory/history?household_id=h1",
        json={"kind": "note", "text": "text"},
    )
    assert created.status_code == 200


def test_oversize_bodies_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    client = TestClient(app)
    sign_in(client, "h1")
    long_text = client.post(
        "/memory/history?household_id=h1",
        json={"kind": "note", "text": "x" * 2001},
    )
    assert long_text.status_code == 422
    long_value = client.put(
        "/memory/preferences/k?household_id=h1", json={"value": "x" * 9000}
    )
    assert long_value.status_code == 422


def test_blank_bodies_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    client = TestClient(app)
    sign_in(client, "h1")
    blank_text = client.post(
        "/memory/history?household_id=h1",
        json={"kind": "note", "text": "   "},
    )
    assert blank_text.status_code == 422
    blank_key = client.put(
        "/memory/preferences/%20%20?household_id=h1", json={"value": 1}
    )
    assert blank_key.status_code == 422
