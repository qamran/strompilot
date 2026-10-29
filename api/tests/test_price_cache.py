"""Tests for the price disk cache."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from strompilot.prices.cache import DiskCache
from strompilot.prices.models import PricePoint, PriceSeries


def make_series(target: date) -> PriceSeries:
    return PriceSeries(
        date=target,
        source="awattar-live",
        attribution="test",
        prices=[
            PricePoint(
                start=datetime(2026, 10, 29, 10, 0, tzinfo=UTC),
                end=datetime(2026, 10, 29, 11, 0, tzinfo=UTC),
                eur_per_mwh=250.0,
            )
        ],
    )


def test_write_then_read_round_trip(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path)
    target = date(2026, 10, 29)
    fetched_at = datetime(2026, 10, 29, 15, 0, tzinfo=UTC)
    cache.write(target, make_series(target), "awattar-live", fetched_at)
    entry = cache.read(target)
    assert entry is not None
    assert entry.source == "awattar-live"
    assert entry.fetched_at == fetched_at
    assert entry.series == make_series(target)


def test_missing_date_reads_none(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path)
    assert cache.read(date(2026, 10, 29)) is None


def test_fetch_marks_round_trip(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path)
    assert cache.last_fetch("awattar") is None
    cache.mark_fetched("awattar", date(2026, 10, 29))
    assert cache.last_fetch("awattar") == date(2026, 10, 29)


def test_old_entry_stays_readable_for_stale_fallback(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path)
    target = date(2026, 10, 29)
    old = datetime(2026, 10, 29, 15, 0, tzinfo=UTC) - timedelta(days=3)
    cache.write(target, make_series(target), "smard-live", old)
    entry = cache.read(target)
    assert entry is not None
    assert entry.fetched_at == old
