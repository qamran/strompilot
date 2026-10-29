"""Tests for the price service fallback order and fair-use guard."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from strompilot.prices.cache import DiskCache
from strompilot.prices.models import PricePoint, PriceSeries
from strompilot.prices.service import get_day_ahead_prices

NOW = datetime(2026, 10, 29, 16, 0, tzinfo=UTC)
TARGET = date(2026, 10, 29)


def make_points(value: float = 250.0) -> list[PricePoint]:
    day_start = datetime(2026, 10, 29, 0, 0, tzinfo=UTC)
    points = []
    for hour in range(24):
        start = day_start + timedelta(hours=hour)
        points.append(
            PricePoint(
                start=start,
                end=start + timedelta(hours=1),
                eur_per_mwh=value,
            )
        )
    return points


def test_fresh_cache_wins_without_live_calls(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path)
    cached = PriceSeries(
        date=TARGET,
        source="awattar-live",
        attribution="cached",
        prices=make_points(),
    )
    cache.write(TARGET, cached, "awattar-live", NOW - timedelta(hours=1))
    calls: list[str] = []

    def fail_awattar(target: date) -> list[PricePoint]:
        calls.append("awattar")
        raise AssertionError("must not fetch")

    def fail_smard(target: date) -> list[PricePoint]:
        calls.append("smard")
        raise AssertionError("must not fetch")

    series = get_day_ahead_prices(TARGET, tmp_path, NOW, fail_awattar, fail_smard)
    assert series.source == "awattar-live"
    assert series.stale is False
    assert calls == []


def test_awattar_live_is_used_and_cached(tmp_path: Path) -> None:
    calls: list[str] = []

    def fake_awattar(target: date) -> list[PricePoint]:
        calls.append("awattar")
        return make_points(200.0)

    def fail_smard(target: date) -> list[PricePoint]:
        calls.append("smard")
        raise AssertionError("must not fetch")

    first = get_day_ahead_prices(TARGET, tmp_path, NOW, fake_awattar, fail_smard)
    assert first.source == "awattar-live"
    assert first.prices[0].eur_per_mwh == 200.0
    second = get_day_ahead_prices(TARGET, tmp_path, NOW, fake_awattar, fail_smard)
    assert second.source == "awattar-live"
    assert calls == ["awattar"]


def test_smard_covers_awattar_outage(tmp_path: Path) -> None:
    def fail_awattar(target: date) -> list[PricePoint]:
        raise ConnectionError("awattar down")

    def fake_smard(target: date) -> list[PricePoint]:
        return make_points(180.0)

    series = get_day_ahead_prices(TARGET, tmp_path, NOW, fail_awattar, fake_smard)
    assert series.source == "smard-live"
    assert "SMARD" in series.attribution


def test_stale_cache_beats_sample(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path)
    cached = PriceSeries(
        date=TARGET,
        source="smard-live",
        attribution="cached",
        prices=make_points(),
    )
    cache.write(TARGET, cached, "smard-live", NOW - timedelta(days=2))

    def fail_awattar(target: date) -> list[PricePoint]:
        raise ConnectionError("awattar down")

    def fail_smard(target: date) -> list[PricePoint]:
        raise ConnectionError("smard down")

    series = get_day_ahead_prices(TARGET, tmp_path, NOW, fail_awattar, fail_smard)
    assert series.source == "smard-live"
    assert series.stale is True


def test_sample_is_last_resort_and_labeled(tmp_path: Path) -> None:
    def fail_awattar(target: date) -> list[PricePoint]:
        raise ConnectionError("awattar down")

    def fail_smard(target: date) -> list[PricePoint]:
        raise ConnectionError("smard down")

    series = get_day_ahead_prices(TARGET, tmp_path, NOW, fail_awattar, fail_smard)
    assert series.source == "sample"
    assert len(series.prices) == 24
    assert "Sample" in series.attribution


def test_guard_skips_source_fetched_today(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path)
    cache.mark_fetched("awattar", NOW.date())
    calls: list[str] = []

    def fail_awattar(target: date) -> list[PricePoint]:
        calls.append("awattar")
        raise AssertionError("guard must skip")

    def fake_smard(target: date) -> list[PricePoint]:
        calls.append("smard")
        return make_points(180.0)

    series = get_day_ahead_prices(TARGET, tmp_path, NOW, fail_awattar, fake_smard)
    assert series.source == "smard-live"
    assert calls == ["smard"]


def test_empty_live_result_falls_through_without_burning_guard(
    tmp_path: Path,
) -> None:
    def empty_awattar(target: date) -> list[PricePoint]:
        return []

    def fake_smard(target: date) -> list[PricePoint]:
        return make_points(180.0)

    series = get_day_ahead_prices(TARGET, tmp_path, NOW, empty_awattar, fake_smard)
    assert series.source == "smard-live"
    assert DiskCache(tmp_path).last_fetch("awattar") is None


def test_corrupt_cache_file_falls_back_to_sample(tmp_path: Path) -> None:
    (tmp_path / "2026-10-29.json").write_text("{not json", encoding="utf-8")

    def fail_awattar(target: date) -> list[PricePoint]:
        raise ConnectionError("awattar down")

    def fail_smard(target: date) -> list[PricePoint]:
        raise ConnectionError("smard down")

    series = get_day_ahead_prices(TARGET, tmp_path, NOW, fail_awattar, fail_smard)
    assert series.source == "sample"


def test_corrupt_fetch_log_is_treated_as_no_marks(tmp_path: Path) -> None:
    (tmp_path / "fetches.json").write_text("{not json", encoding="utf-8")
    calls: list[str] = []

    def fake_awattar(target: date) -> list[PricePoint]:
        calls.append("awattar")
        return make_points(200.0)

    def fail_smard(target: date) -> list[PricePoint]:
        raise AssertionError("must not fetch")

    series = get_day_ahead_prices(TARGET, tmp_path, NOW, fake_awattar, fail_smard)
    assert series.source == "awattar-live"
    assert calls == ["awattar"]


def test_guard_uses_berlin_day(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path)
    cache.mark_fetched("awattar", date(2026, 10, 30))
    now = datetime(2026, 10, 29, 23, 30, tzinfo=UTC)
    calls: list[str] = []

    def fail_awattar(target: date) -> list[PricePoint]:
        calls.append("awattar")
        raise AssertionError("guard must skip")

    def fake_smard(target: date) -> list[PricePoint]:
        calls.append("smard")
        return make_points(180.0)

    series = get_day_ahead_prices(
        date(2026, 10, 30), tmp_path, now, fail_awattar, fake_smard
    )
    assert series.source == "smard-live"
    assert calls == ["smard"]
