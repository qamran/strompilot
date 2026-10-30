"""Tests for the monthly report math and art prompt."""

import json
from datetime import date

import pytest

from strompilot.lifeplan.schemas import PriceBar
from strompilot.report.monthly import art_prompt, build_month
from strompilot.tariff.profiles import DATA_PATH


def flat_bars(day: date, ct: float) -> list[PriceBar]:
    """Build 24 Berlin-hour bars at one flat rate."""
    return [PriceBar(hour=hour, price_ct_kwh=ct, source="test") for hour in range(24)]


def test_june_day_matches_h25_shape() -> None:
    report = build_month(
        2026, 6, 3650.0, lambda day: (flat_bars(day, 30.0), False), 40.0
    )
    assert report.month == "2026-06"
    assert len(report.days) == 30
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    profile = raw["months"]["6"]["WT"]
    expected_kwh = round(3650.0 * sum(profile) / 1_000_000, 2)
    first = report.days[0]
    assert first.day == "2026-06-01"
    assert first.kwh == expected_kwh
    assert first.cost_eur == round(expected_kwh * 0.30, 2)
    assert first.sample is False


def test_totals_aggregate_days() -> None:
    report = build_month(
        2026, 2, 3650.0, lambda day: (flat_bars(day, 30.0), False), 40.0
    )
    assert len(report.days) == 28
    assert report.total_kwh == round(sum(day.kwh for day in report.days), 2)
    assert report.total_cost_eur == round(sum(day.cost_eur for day in report.days), 2)
    assert report.savings_eur == round(
        report.total_kwh * 0.40 - report.total_cost_eur, 2
    )
    assert report.sample_days == 0


def test_savings_can_go_negative_honestly() -> None:
    report = build_month(
        2026, 2, 3650.0, lambda day: (flat_bars(day, 50.0), True), 40.0
    )
    assert report.savings_eur < 0
    assert report.sample_days == 28
    assert all(day.sample for day in report.days)


def test_worst_hour_names_day_and_rate() -> None:
    def loader(day: date) -> tuple[list[PriceBar], bool]:
        bars = flat_bars(day, 30.0)
        if day.day == 15:
            bars = [bar.model_copy(update={"price_ct_kwh": 90.0}) for bar in bars]
        return bars, False

    report = build_month(2026, 6, 3650.0, loader, 40.0)
    assert report.worst_hour is not None
    assert report.worst_hour.day == "2026-06-15"
    assert report.worst_hour.price_ct_kwh == 90.0


def test_cheapest_window_reported_per_day() -> None:
    bars = flat_bars(date(2026, 6, 1), 30.0)
    bars[2] = bars[2].model_copy(update={"price_ct_kwh": 10.0})
    bars[3] = bars[3].model_copy(update={"price_ct_kwh": 12.0})
    report = build_month(2026, 6, 3650.0, lambda day: (bars, False), 40.0)
    window = report.days[0].cheapest_window
    assert window is not None
    assert (window.start, window.end) == ("02:00", "04:00")


def test_bad_month_rejected() -> None:
    with pytest.raises(ValueError, match="month"):
        build_month(2026, 13, 3650.0, lambda day: (flat_bars(day, 30.0), False), 40.0)


def test_art_prompt_names_month_without_numbers() -> None:
    prompt = art_prompt("2026-06")
    assert "Juni" in prompt
    assert "2026" not in prompt
    assert "kWh" not in prompt
    assert "KI-generiert" not in prompt


def test_art_prompt_rejects_bad_month() -> None:
    with pytest.raises(ValueError, match="month"):
        art_prompt("June 2026")
