"""Tests for the price feed data models."""

from datetime import UTC, date, datetime

from strompilot.prices.models import PricePoint, PriceSeries


def make_point(eur_per_mwh: float = 250.0) -> PricePoint:
    return PricePoint(
        start=datetime(2026, 10, 29, 10, 0, tzinfo=UTC),
        end=datetime(2026, 10, 29, 11, 0, tzinfo=UTC),
        eur_per_mwh=eur_per_mwh,
    )


def test_ct_per_kwh_conversion() -> None:
    assert make_point(250.0).ct_per_kwh == 25.0


def test_series_carries_source_and_attribution() -> None:
    series = PriceSeries(
        date=date(2026, 10, 29),
        source="awattar-live",
        attribution="EPEX Spot day-ahead prices via aWATTar",
        prices=[make_point()],
    )
    assert series.stale is False
    assert series.unit == "Eur/MWh"
    assert len(series.prices) == 1
