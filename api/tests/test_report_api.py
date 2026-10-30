"""Tests for the monthly report HTTP API."""

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from strompilot.main import app, get_image_client


class FakeImages:
    """Scripted image generator that records prompts."""

    def __init__(self, art: bytes) -> None:
        self._art = art
        self.prompts: list[str] = []

    def generate(self, prompt: str, size: str = "1536x1024") -> bytes:
        del size
        self.prompts.append(prompt)
        return self._art


@pytest.fixture
def report_setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    """Test client with scratch storage and flat cached prices."""
    from datetime import UTC, datetime

    from strompilot.prices.cache import DiskCache
    from tests.fakes import day_series

    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    monkeypatch.setenv("REPORT_ART_DIR", str(tmp_path / "art"))
    cache_dir = tmp_path / "prices"
    cache_dir.mkdir()
    monkeypatch.setenv("PRICE_CACHE_DIR", str(cache_dir))
    cache = DiskCache(cache_dir)
    for day_number in range(1, 29):
        day = date(2026, 2, day_number)
        cache.write(day, day_series([25.0] * 24, day), "test", datetime.now(UTC))
    app.dependency_overrides[get_image_client] = lambda: FakeImages(b"art-bytes")
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_monthly_report_totals(report_setup: TestClient) -> None:
    response = report_setup.get("/report/monthly?household_id=h1&month=2026-02")
    assert response.status_code == 200
    payload = response.json()
    report = payload["report"]
    assert report["month"] == "2026-02"
    assert len(report["days"]) == 28
    assert report["total_kwh"] > 0
    assert report["worst_hour"] is not None
    assert report["sample_days"] == 0
    assert len(report["assumptions"]) == 3
    assert payload["illustration_data_url"] is None


def test_report_speaks_english_when_asked(report_setup: TestClient) -> None:
    response = report_setup.get("/report/monthly?household_id=h1&month=2026-02&lang=en")
    assert response.status_code == 200
    joined = " ".join(response.json()["report"]["assumptions"])
    assert "Annual use" in joined
    assert "quarter-hourly" in joined


def test_illustration_generates_once_then_caches(
    report_setup: TestClient,
) -> None:
    first = report_setup.post(
        "/report/monthly/illustration?household_id=h1&month=2026-02"
    )
    assert first.status_code == 200
    assert first.json()["cached"] is False
    assert first.json()["illustration_data_url"].startswith("data:image/png;base64,")
    second = report_setup.post(
        "/report/monthly/illustration?household_id=h1&month=2026-02"
    )
    assert second.json()["cached"] is True
    assert (
        second.json()["illustration_data_url"] == first.json()["illustration_data_url"]
    )
    report = report_setup.get("/report/monthly?household_id=h1&month=2026-02")
    assert (
        report.json()["illustration_data_url"] == first.json()["illustration_data_url"]
    )


def test_bad_month_rejected(report_setup: TestClient) -> None:
    assert (
        report_setup.get("/report/monthly?household_id=h1&month=soon").status_code
        == 422
    )
    assert (
        report_setup.get("/report/monthly?household_id=h1&month=2999-01").status_code
        == 422
    )


def test_blank_household_rejected(report_setup: TestClient) -> None:
    assert (
        report_setup.get("/report/monthly?household_id=+&month=2026-02").status_code
        == 422
    )


def test_missing_keys_returns_500(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    monkeypatch.setenv("REPORT_ART_DIR", str(tmp_path / "art"))
    monkeypatch.delenv("META_API_KEY", raising=False)
    client = TestClient(app)
    response = client.post("/report/monthly/illustration?household_id=h1&month=2026-02")
    assert response.status_code == 500
