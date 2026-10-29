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
