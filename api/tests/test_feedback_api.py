"""Tests for the feedback HTTP API."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from strompilot.main import app


@pytest.fixture
def feedback_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Test client with memory on a scratch database."""
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    return TestClient(app)


def test_feedback_stored_and_shifts_prefs(feedback_setup: TestClient) -> None:
    sent = feedback_setup.post(
        "/feedback?household_id=h1",
        json={"device": "Waschmaschine", "verdict": "too_early"},
    )
    assert sent.status_code == 200
    payload = sent.json()
    assert payload["episode"]["kind"] == "feedback"
    assert "Waschmaschine" in payload["episode"]["text"]
    assert payload["learned_windows"] == {
        "Waschmaschine": {"earliest_shift_h": 1, "latest_shift_h": 0}
    }
    again = feedback_setup.post(
        "/feedback?household_id=h1",
        json={"device": "Waschmaschine", "verdict": "too_early", "note": "zu laut"},
    )
    assert again.json()["learned_windows"]["Waschmaschine"]["earliest_shift_h"] == 2
    stored = feedback_setup.get("/memory/preferences?household_id=h1")
    assert stored.json()["preferences"]["learned_windows"] == {
        "Waschmaschine": {"earliest_shift_h": 2, "latest_shift_h": 0}
    }


def test_feedback_lists_per_household(feedback_setup: TestClient) -> None:
    feedback_setup.post(
        "/feedback?household_id=h1",
        json={"device": "E-Auto", "verdict": "too_late"},
    )
    listed = feedback_setup.get("/feedback?household_id=h1")
    assert listed.status_code == 200
    assert [episode["kind"] for episode in listed.json()["feedback"]] == ["feedback"]
    assert feedback_setup.get("/feedback?household_id=h2").json()["feedback"] == []


def test_bad_verdict_rejected(feedback_setup: TestClient) -> None:
    response = feedback_setup.post(
        "/feedback?household_id=h1",
        json={"device": "Waschmaschine", "verdict": "meh"},
    )
    assert response.status_code == 422


def test_blank_device_rejected(feedback_setup: TestClient) -> None:
    response = feedback_setup.post(
        "/feedback?household_id=h1",
        json={"device": "  ", "verdict": "good"},
    )
    assert response.status_code == 422


def test_blank_household_rejected(feedback_setup: TestClient) -> None:
    response = feedback_setup.post(
        "/feedback?household_id=+",
        json={"device": "Waschmaschine", "verdict": "good"},
    )
    assert response.status_code == 422
    assert feedback_setup.get("/feedback?household_id=+").status_code == 422
