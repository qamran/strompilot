"""Tests for the Flex-Alarm window scanner."""

import pytest

from strompilot.flexalarm.models import AlertCandidate
from strompilot.flexalarm.watch import scan_windows
from tests.fakes import day_series


def flat_day() -> list[float]:
    """Boring day: nothing worth flagging on its own."""
    return [25.0] * 24


def test_cheap_window_finds_the_lowest_two_hours() -> None:
    prices = flat_day()
    prices[2] = 8.0
    prices[3] = 9.0
    found = {c.kind: c for c in scan_windows(day_series(prices))}
    cheap = found["cheap_window"]
    assert (cheap.start, cheap.end) == ("02:00", "04:00")
    assert cheap.avg_ct_kwh == pytest.approx(8.5)
    assert cheap.mean_ct_kwh == pytest.approx(round(sum(prices) / 24, 2))
    assert isinstance(cheap, AlertCandidate)


def test_spike_needs_a_real_outlier() -> None:
    kinds = {c.kind for c in scan_windows(day_series(flat_day()))}
    assert "price_spike" not in kinds
    prices = flat_day()
    prices[18] = 60.0
    found = {c.kind: c for c in scan_windows(day_series(prices))}
    spike = found["price_spike"]
    assert (spike.start, spike.end) == ("18:00", "19:00")
    assert spike.extreme_ct_kwh == pytest.approx(60.0)


def test_negative_stretch_covers_every_negative_hour() -> None:
    prices = flat_day()
    prices[11] = -2.0
    prices[12] = -5.0
    prices[13] = -1.0
    found = {c.kind: c for c in scan_windows(day_series(prices))}
    stretch = found["negative_prices"]
    assert (stretch.start, stretch.end) == ("11:00", "14:00")
    assert stretch.extreme_ct_kwh == pytest.approx(-5.0)


def test_no_negative_hours_means_no_negative_candidate() -> None:
    kinds = {c.kind for c in scan_windows(day_series(flat_day()))}
    assert "negative_prices" not in kinds


def test_empty_series_scans_to_nothing() -> None:
    assert scan_windows(day_series([])) == []


def test_negative_stretch_suppresses_same_window_cheap() -> None:
    prices = flat_day()
    prices[2] = -4.0
    prices[3] = -5.0
    kinds = [c.kind for c in scan_windows(day_series(prices))]
    assert kinds == ["negative_prices"]


def test_disjoint_cheap_and_negative_windows_both_fire() -> None:
    prices = flat_day()
    prices[12] = -1.0
    prices[2] = 8.0
    prices[3] = 9.0
    found = {c.kind: c for c in scan_windows(day_series(prices))}
    assert found["cheap_window"].start == "02:00"
    assert found["negative_prices"].start == "12:00"


def test_cheap_window_reports_its_day() -> None:
    from datetime import date

    (cheap,) = [
        c for c in scan_windows(day_series(flat_day())) if c.kind == "cheap_window"
    ]
    assert cheap.day == date(2026, 6, 1)
