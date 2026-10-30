"""Tests for the Flex-Alarm HTTP API."""

from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from strompilot.main import app, get_watch_router
from strompilot.prices.cache import DiskCache
from tests.fakes import FakeRouter, day_series, reply


def seed_prices(cache_dir: Path, target: date) -> None:
    """Seed one cached price day with a cheap window and a spike."""
    prices = [25.0] * 24
    prices[2] = 8.0
    prices[3] = 9.0
    prices[18] = 60.0
    DiskCache(cache_dir).write(
        target, day_series(prices, target), "test", datetime.now(UTC)
    )


@pytest.fixture
def watch_setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    """Test client with a scripted watcher and seeded prices."""
    cache_dir = tmp_path / "prices"
    cache_dir.mkdir()
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    monkeypatch.setenv("PRICE_CACHE_DIR", str(cache_dir))
    seed_prices(cache_dir, date(2026, 6, 1))
    router = FakeRouter({"watcher": [reply('{"fire": true, "reason": "gut"}')] * 10})
    app.dependency_overrides[get_watch_router] = lambda: router
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_watch_fires_and_lists_alerts(watch_setup: TestClient) -> None:
    run = watch_setup.post("/flexalarm/watch?household_id=h1&date=2026-06-01")
    assert run.status_code == 200
    report = run.json()
    assert report["household_id"] == "h1"
    assert report["candidates"] == 2
    assert report["fired"] == 2
    assert report["delivered"] + report["held"] == 2
    listed = watch_setup.get("/flexalarm/alerts?household_id=h1")
    assert listed.status_code == 200
    assert len(listed.json()["alerts"]) == 2


def test_watch_speaks_english_when_asked(watch_setup: TestClient) -> None:
    run = watch_setup.post("/flexalarm/watch?household_id=h1&date=2026-06-01&lang=en")
    assert run.status_code == 200
    listed = watch_setup.get("/flexalarm/alerts?household_id=h1")
    bodies = " ".join(alert["body"] for alert in listed.json()["alerts"])
    titles = " ".join(alert["title"] for alert in listed.json()["alerts"])
    assert "on average" in bodies
    assert "Cheap power" in titles or "Power spike" in titles


def test_watch_rerun_dedups(watch_setup: TestClient) -> None:
    first = watch_setup.post("/flexalarm/watch?household_id=h1&date=2026-06-01")
    assert first.json()["fired"] == 2
    second = watch_setup.post("/flexalarm/watch?household_id=h1&date=2026-06-01")
    assert second.status_code == 200
    assert second.json()["duplicates"] == 2
    listed = watch_setup.get("/flexalarm/alerts?household_id=h1")
    assert len(listed.json()["alerts"]) == 2


def test_watch_defaults_to_tomorrow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from zoneinfo import ZoneInfo

    cache_dir = tmp_path / "prices"
    cache_dir.mkdir()
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    monkeypatch.setenv("PRICE_CACHE_DIR", str(cache_dir))
    tomorrow = datetime.now(ZoneInfo("Europe/Berlin")).date()
    from datetime import timedelta

    tomorrow = tomorrow + timedelta(days=1)
    seed_prices(cache_dir, tomorrow)
    router = FakeRouter({"watcher": [reply('{"fire": true, "reason": "gut"}')] * 10})
    app.dependency_overrides[get_watch_router] = lambda: router
    try:
        run = TestClient(app).post("/flexalarm/watch?household_id=h1")
    finally:
        app.dependency_overrides.clear()
    assert run.status_code == 200
    assert run.json()["day"] == tomorrow.isoformat()


def test_blank_household_rejected(watch_setup: TestClient) -> None:
    assert (
        watch_setup.post("/flexalarm/watch?household_id=+&date=2026-06-01").status_code
        == 422
    )
    assert watch_setup.get("/flexalarm/alerts?household_id=+").status_code == 422


def test_missing_keys_returns_500(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    client = TestClient(app)
    assert client.post("/flexalarm/watch?household_id=h1").status_code == 500
