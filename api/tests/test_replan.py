"""Tests for calibration-aware plan totals and the re-plan diff."""

from datetime import UTC, date, datetime, timedelta

from strompilot.metervision.replan import day_plan_totals, diff_totals, plan_totals
from strompilot.tariff.profiles import HourlyBaseline
from tests.fakes import make_device, price_bars


def flat_baseline(day: date, kwh_per_hour: float) -> list[HourlyBaseline]:
    """Build 24 UTC hours of flat background use for one Berlin day."""
    start = datetime(day.year, day.month, day.day, 0, 0, tzinfo=UTC)
    hours = []
    for offset in range(24):
        hours.append(
            HourlyBaseline(
                start=start + timedelta(hours=offset),
                end=start + timedelta(hours=offset + 1),
                kwh=kwh_per_hour,
            )
        )
    return hours


def test_totals_add_devices_and_background() -> None:
    day = date(2026, 6, 1)
    totals = plan_totals([make_device()], price_bars(), flat_baseline(day, 0.1), day)
    assert totals.device_cost_eur == 0.60
    assert totals.baseline_kwh == 2.4
    assert totals.baseline_cost_eur == 0.70
    assert totals.total_eur == 1.30
    assert totals.slots == 1


def test_diff_flags_changed_background_and_same_devices() -> None:
    day = date(2026, 6, 1)
    before = plan_totals([make_device()], price_bars(), flat_baseline(day, 0.1), day)
    after = plan_totals([make_device()], price_bars(), flat_baseline(day, 0.2), day)
    diff = diff_totals(before, after)
    assert diff.devices_unchanged is True
    assert diff.before.total_eur == 1.30
    assert diff.after.total_eur == 1.99
    assert "Waschmaschine" not in diff.note
    assert "Hintergrund" in diff.note


def test_day_totals_scale_linearly_with_annual_use() -> None:
    day = date(2026, 6, 1)
    small = day_plan_totals([make_device()], price_bars(), 1825.0, day)
    big = day_plan_totals([make_device()], price_bars(), 3650.0, day)
    assert big.baseline_kwh == 2.0 * small.baseline_kwh
    assert big.device_cost_eur == small.device_cost_eur == 0.60
    assert 5.0 < small.baseline_kwh < 20.0
