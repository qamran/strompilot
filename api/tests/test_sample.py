"""Tests for the labeled sample fallback."""

from datetime import date
from zoneinfo import ZoneInfo

from strompilot.prices.sample import sample_series

BERLIN = ZoneInfo("Europe/Berlin")


def test_sample_covers_24_hours_and_is_deterministic() -> None:
    target = date(2026, 10, 29)
    first = sample_series(target)
    second = sample_series(target)
    assert first == second
    assert first.source == "sample"
    assert len(first.prices) == 24
    assert all(p.start.astimezone(BERLIN).date() == target for p in first.prices)
    values = [p.eur_per_mwh for p in first.prices]
    assert min(values) > 0
    assert max(values) > min(values)


def test_spring_forward_day_has_23_hours() -> None:
    target = date(2026, 3, 29)
    series = sample_series(target)
    assert len(series.prices) == 23
    assert all(p.start.astimezone(BERLIN).date() == target for p in series.prices)


def test_fall_back_day_has_25_hours() -> None:
    target = date(2026, 10, 25)
    series = sample_series(target)
    assert len(series.prices) == 25
    assert all(p.start.astimezone(BERLIN).date() == target for p in series.prices)
