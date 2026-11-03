"""Tests for the all-in price bar loader."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from strompilot.lifeplan.loaders import load_price_bars
from strompilot.prices.models import PricePoint
from strompilot.tariff.defaults import DEFAULTS
from strompilot.tariff.engine import decompose


def test_loader_builds_all_in_bars(tmp_path: Path) -> None:
    target = date(2026, 1, 15)
    base = datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
    points = [
        PricePoint(
            start=base + timedelta(hours=n),
            end=base + timedelta(hours=n + 1),
            eur_per_mwh=100.0,
        )
        for n in range(3)
    ]
    loaded = load_price_bars(
        target,
        tmp_path,
        datetime(2026, 1, 14, 12, 0, tzinfo=UTC),
        DEFAULTS,
        awattar_fetcher=lambda day: points,
    )
    assert loaded.source == "awattar-live"
    assert loaded.stale is False
    assert [bar.hour for bar in loaded.bars] == [1, 2, 3]
    expected = decompose(100.0, DEFAULTS).total
    assert [bar.price_ct_kwh for bar in loaded.bars] == [expected] * 3
    assert all(bar.source == "awattar-live" for bar in loaded.bars)


def test_loader_keys_bars_by_utc_start(tmp_path: Path) -> None:
    target = date(2026, 10, 25)
    base = datetime(2026, 10, 24, 22, 0, tzinfo=UTC)
    points = [
        PricePoint(
            start=base + timedelta(hours=n),
            end=base + timedelta(hours=n + 1),
            eur_per_mwh=100.0,
        )
        for n in range(25)
    ]
    loaded = load_price_bars(
        target,
        tmp_path,
        datetime(2026, 10, 24, 12, 0, tzinfo=UTC),
        DEFAULTS,
        awattar_fetcher=lambda day: points,
    )
    assert len(loaded.bars) == 25
    assert [bar.hour for bar in loaded.bars].count(2) == 2
    starts = [bar.start_utc for bar in loaded.bars]
    assert all(isinstance(start, str) for start in starts)
    assert len(set(starts)) == 25
    ordered = [start for start in starts if isinstance(start, str)]
    assert ordered == sorted(ordered)


def test_loader_drops_duplicate_instants(tmp_path: Path) -> None:
    target = date(2026, 1, 15)
    base = datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
    point = PricePoint(start=base, end=base + timedelta(hours=1), eur_per_mwh=50.0)
    other = PricePoint(
        start=base + timedelta(hours=1),
        end=base + timedelta(hours=2),
        eur_per_mwh=60.0,
    )
    loaded = load_price_bars(
        target,
        tmp_path,
        datetime(2026, 1, 14, 12, 0, tzinfo=UTC),
        DEFAULTS,
        awattar_fetcher=lambda day: [point, point, other],
    )
    assert [bar.price_ct_kwh for bar in loaded.bars] == [
        decompose(50.0, DEFAULTS).total,
        decompose(60.0, DEFAULTS).total,
    ]


def test_loader_falls_back_to_sample(tmp_path: Path) -> None:
    def failing(day: date) -> list[PricePoint]:
        raise ConnectionError("no network")

    loaded = load_price_bars(
        date(2026, 1, 15),
        tmp_path,
        datetime(2026, 1, 14, 12, 0, tzinfo=UTC),
        DEFAULTS,
        awattar_fetcher=failing,
        smard_fetcher=failing,
    )
    assert loaded.source == "sample"
    assert len(loaded.bars) == 24
