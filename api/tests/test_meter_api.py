"""Tests for the meter vision HTTP API."""

import io
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from strompilot.main import app, get_meter_vision
from strompilot.metervision.pipeline import MeterVision
from strompilot.prices.cache import DiskCache
from tests.fakes import FakeRouter, FakeSam, day_series, reply


def png() -> bytes:
    """100x100 red PNG upload."""
    image = Image.new("RGB", (100, 100), (255, 0, 0))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def vision(boxes: list[Any], analyst: list[Any]) -> MeterVision:
    """Scripted vision deps: SAM boxes plus analyst replies."""
    return MeterVision(
        router=FakeRouter({"analyst": analyst}),
        sam=FakeSam(boxes),
    )


@pytest.fixture
def meter_setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, Path]]:
    """Test client with scripted vision on scratch storage."""
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    monkeypatch.setenv("METER_PHOTOS_DIR", str(tmp_path / "photos"))
    cache_dir = tmp_path / "prices"
    cache_dir.mkdir()
    monkeypatch.setenv("PRICE_CACHE_DIR", str(cache_dir))
    DiskCache(cache_dir).write(
        date(2026, 6, 2),
        day_series([25.0] * 24, date(2026, 6, 2)),
        "test",
        datetime.now(UTC),
    )
    app.dependency_overrides[get_meter_vision] = lambda: vision(
        [[], []], [reply('{"value_kwh": 100.0, "confidence": "high"}')] * 4
    )
    yield TestClient(app), tmp_path
    app.dependency_overrides.clear()


def seed_confirmed(db_path: Path, value_kwh: float, days_ago: int) -> dict[str, object]:
    """Seed one confirmed reading days ago, bypassing vision."""
    from strompilot.metervision.store import MeterStore

    store = MeterStore(db_path / "memory.db")
    proposed = store.propose(
        household_id="h1",
        value_kwh=value_kwh,
        read_at=datetime.now(UTC) - timedelta(days=days_ago),
        confidence="high",
        sam_box=None,
        photo_path="seed.png",
    )
    confirmed = store.confirm("h1", proposed.id, corrected_kwh=None)
    return {"id": confirmed.id, "value_kwh": confirmed.value_kwh}


def upload(client: TestClient, photo: bytes, name: str = "meter.png") -> object:
    """Upload one photo for household h1."""
    response = client.post(
        "/meter/readings?household_id=h1",
        files={"file": (name, photo, "image/png")},
    )
    assert response.status_code == 200
    return response.json()


def test_intake_proposes_and_lists(
    meter_setup: tuple[TestClient, Path],
) -> None:
    client, _ = meter_setup
    created = upload(client, png())
    assert isinstance(created, dict)
    assert created["status"] == "proposed"
    assert created["value_kwh"] == 100.0
    assert created["id"] == 1
    assert "/" not in created["photo_path"] and "\\" not in created["photo_path"]
    listed = client.get("/meter/readings?household_id=h1")
    assert listed.status_code == 200
    assert len(listed.json()["readings"]) == 1


def test_first_confirm_has_no_calibration(
    meter_setup: tuple[TestClient, Path],
) -> None:
    client, _ = meter_setup
    created = upload(client, png())
    assert isinstance(created, dict)
    decided = client.post(
        f"/meter/readings/{created['id']}/confirm?household_id=h1", json={}
    )
    assert decided.status_code == 200
    payload = decided.json()
    assert payload["reading"]["status"] == "confirmed"
    assert payload["calibration"] is None
    assert payload["diff"] is None
    assert "weiterer" in payload["note"]


def test_second_confirm_calibrates_and_diffs(
    meter_setup: tuple[TestClient, Path],
) -> None:
    client, tmp_path = meter_setup
    first = seed_confirmed(tmp_path, 100.0, days_ago=10)
    second = upload(client, png())
    assert isinstance(second, dict)
    decided = client.post(
        f"/meter/readings/{second['id']}/confirm?household_id=h1",
        json={
            "corrected_value_kwh": 200.0,
            "target_date": "2026-06-02",
            "devices": [
                {
                    "device": "Waschmaschine",
                    "power_kw": 2.0,
                    "duration_h": 2.0,
                    "earliest": "00:00",
                    "latest": "23:00",
                    "shiftable": True,
                }
            ],
        },
    )
    assert decided.status_code == 200
    payload = decided.json()
    assert payload["reading"]["value_kwh"] == 200.0
    assert payload["calibration"] is not None
    assert payload["calibration"]["kwh_per_day"] == 10.0
    assert payload["calibration"]["annual_kwh"] == 3650.0
    assert payload["calibration"]["from_reading_id"] == first["id"]
    assert payload["diff"]["devices_unchanged"] is True
    stored = client.get("/memory/preferences?household_id=h1")
    assert (
        stored.json()["preferences"]["annual_kwh"]
        == payload["calibration"]["annual_kwh"]
    )


def test_proposed_readings_never_enter_math(
    meter_setup: tuple[TestClient, Path],
) -> None:
    client, tmp_path = meter_setup
    first = seed_confirmed(tmp_path, 100.0, days_ago=10)
    stray = upload(client, png())
    assert isinstance(stray, dict)
    third = upload(client, png())
    assert isinstance(third, dict)
    decided = client.post(
        f"/meter/readings/{third['id']}/confirm?household_id=h1",
        json={"corrected_value_kwh": 200.0},
    )
    calibration = decided.json()["calibration"]
    assert calibration is not None
    assert calibration["from_reading_id"] == first["id"]
    assert calibration["to_reading_id"] == third["id"]


def test_photos_not_stored_by_default(
    meter_setup: tuple[TestClient, Path],
) -> None:
    client, tmp_path = meter_setup
    created = upload(client, png())
    assert isinstance(created, dict)
    assert created["photo_path"] == ""
    assert not (tmp_path / "photos").exists()


def test_keep_photo_stores_with_consent(
    meter_setup: tuple[TestClient, Path],
) -> None:
    client, tmp_path = meter_setup
    response = client.post(
        "/meter/readings?household_id=h1&keep_photo=true",
        files={"file": ("meter.png", png(), "image/png")},
    )
    assert response.status_code == 200
    name = response.json()["photo_path"]
    assert name.endswith(".png")
    assert (tmp_path / "photos" / name).exists()


def test_unknown_reading_returns_404(
    meter_setup: tuple[TestClient, Path],
) -> None:
    client, _ = meter_setup
    decided = client.post("/meter/readings/999/confirm?household_id=h1", json={})
    assert decided.status_code == 404


def test_blank_household_rejected(
    meter_setup: tuple[TestClient, Path],
) -> None:
    client, _ = meter_setup
    response = client.post(
        "/meter/readings?household_id=+",
        files={"file": ("meter.png", png(), "image/png")},
    )
    assert response.status_code == 422
    assert client.get("/meter/readings?household_id=+").status_code == 422


def test_non_image_rejected(meter_setup: tuple[TestClient, Path]) -> None:
    client, _ = meter_setup
    response = client.post(
        "/meter/readings?household_id=h1",
        files={"file": ("notes.txt", b"4217", "text/plain")},
    )
    assert response.status_code == 422


def test_oversize_photo_rejected(meter_setup: tuple[TestClient, Path]) -> None:
    client, _ = meter_setup
    response = client.post(
        "/meter/readings?household_id=h1",
        files={"file": ("big.png", b"x" * (11 * 1024 * 1024), "image/png")},
    )
    assert response.status_code == 422


def test_vision_failure_returns_502(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from strompilot.llm.types import LlmError

    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    monkeypatch.setenv("METER_PHOTOS_DIR", str(tmp_path / "photos"))
    app.dependency_overrides[get_meter_vision] = lambda: vision(
        [[]], [LlmError("spark down")]
    )
    try:
        response = TestClient(app).post(
            "/meter/readings?household_id=h1",
            files={"file": ("meter.png", png(), "image/png")},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 502


def test_missing_keys_returns_500(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    monkeypatch.setenv("METER_PHOTOS_DIR", str(tmp_path / "photos"))
    monkeypatch.delenv("META_API_KEY", raising=False)
    client = TestClient(app)
    response = client.post(
        "/meter/readings?household_id=h1",
        files={"file": ("meter.png", png(), "image/png")},
    )
    assert response.status_code == 500
