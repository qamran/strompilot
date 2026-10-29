"""Tests for the memory HTTP API."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from strompilot.main import app


def test_preference_crud_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    client = TestClient(app)
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
    client.put("/memory/preferences/k?household_id=h1", json={"value": "a"})
    created = client.post(
        "/memory/history?household_id=h1",
        json={"kind": "note", "text": "privat"},
    )
    episode_id = created.json()["id"]
    assert client.get("/memory/preferences?household_id=h2").json()["preferences"] == {}
    assert client.get("/memory/history?household_id=h2").json()["episodes"] == []
    assert (
        client.delete(f"/memory/history/{episode_id}?household_id=h2").status_code
        == 404
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
    client.put("/memory/preferences/k?household_id=h1", json={"value": "a"})
    client.post(
        "/memory/history?household_id=h1",
        json={"kind": "note", "text": "vergiss mich"},
    )
    client.put("/memory/preferences/k?household_id=h2", json={"value": "b"})
    forgotten = client.delete("/memory/household?household_id=h1")
    assert forgotten.status_code == 200
    assert client.get("/memory/preferences?household_id=h1").json()["preferences"] == {}
    assert client.get("/memory/history?household_id=h1").json()["episodes"] == []
    assert client.get("/memory/preferences?household_id=h2").json()["preferences"] == {
        "k": "b"
    }


def test_blank_household_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    client = TestClient(app)
    response = client.get("/memory/preferences?household_id=%20%20")
    assert response.status_code == 422
    created = client.post(
        "/memory/history?household_id=h1",
        json={"kind": "note", "text": "text"},
    )
    assert created.status_code == 200


def test_blank_bodies_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    client = TestClient(app)
    blank_text = client.post(
        "/memory/history?household_id=h1",
        json={"kind": "note", "text": "   "},
    )
    assert blank_text.status_code == 422
    blank_key = client.put(
        "/memory/preferences/%20%20?household_id=h1", json={"value": 1}
    )
    assert blank_key.status_code == 422
