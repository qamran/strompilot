"""Tests for the day-ahead prices endpoint."""

from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

import strompilot.prices.awattar as awattar_client
import strompilot.prices.smard as smard_client
from strompilot.main import app
from strompilot.prices.cache import DiskCache
from strompilot.prices.models import PricePoint, PriceSeries


def _fail_awattar(target: date) -> list[PricePoint]:
    raise ConnectionError("awattar down")


def _fail_smard(target: date) -> list[PricePoint]:
    raise ConnectionError("smard down")


def test_sample_fallback_is_served_labeled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PRICE_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(awattar_client, "fetch_awattar", _fail_awattar)
    monkeypatch.setattr(smard_client, "fetch_smard", _fail_smard)
    response = TestClient(app).get("/prices/day-ahead?date=2026-10-29")
    assert response.status_code == 200
    payload = response.json()
    assert payload["date"] == "2026-10-29"
    assert payload["source"] == "sample"
    assert payload["stale"] is False
    assert len(payload["prices"]) == 24


def test_fresh_cache_is_served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRICE_CACHE_DIR", str(tmp_path))
    cache = DiskCache(tmp_path)
    now = datetime.now(UTC)
    series = PriceSeries(
        date=date(2026, 10, 29),
        source="awattar-live",
        attribution="cached",
        prices=[
            PricePoint(
                start=datetime(2026, 10, 29, 0, 0, tzinfo=UTC),
                end=datetime(2026, 10, 29, 1, 0, tzinfo=UTC),
                eur_per_mwh=250.0,
            )
        ],
    )
    cache.write(date(2026, 10, 29), series, "awattar-live", now)
    response = TestClient(app).get("/prices/day-ahead?date=2026-10-29")
    assert response.status_code == 200
    assert response.json()["source"] == "awattar-live"


def test_default_date_is_berlin_today(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PRICE_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(awattar_client, "fetch_awattar", _fail_awattar)
    monkeypatch.setattr(smard_client, "fetch_smard", _fail_smard)
    response = TestClient(app).get("/prices/day-ahead")
    assert response.status_code == 200
    expected = datetime.now(ZoneInfo("Europe/Berlin")).date().isoformat()
    assert response.json()["date"] == expected
