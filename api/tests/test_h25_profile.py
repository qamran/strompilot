"""Tests for the H25 household baseline."""

import json
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from strompilot.tariff.profiles import baseline_day, day_type, load_h25

BERLIN = ZoneInfo("Europe/Berlin")


def test_h25_loads_twelve_months_of_quarters() -> None:
    data = load_h25()
    assert len(data.months) == 12
    for month in data.months.values():
        for series in month.values():
            assert len(series) == 96
            assert all(value > 0 for value in series)


def test_day_type_mapping() -> None:
    assert day_type(date(2026, 10, 29)) == "WT"
    assert day_type(date(2026, 10, 31)) == "SA"
    assert day_type(date(2026, 11, 1)) == "FT"


def test_baseline_day_covers_berlin_hours() -> None:
    target = date(2026, 10, 29)
    hours = baseline_day(target, 3500.0)
    assert len(hours) == 24
    assert all(h.start.astimezone(BERLIN).date() == target for h in hours)
    assert all(h.end - h.start == timedelta(hours=1) for h in hours)
    assert all(h.kwh > 0 for h in hours)


def test_baseline_day_handles_dst_days() -> None:
    assert len(baseline_day(date(2026, 3, 29), 3500.0)) == 23
    assert len(baseline_day(date(2026, 10, 25), 3500.0)) == 25


def test_meta_points_to_real_h25_publication() -> None:
    from strompilot.tariff.profiles import DATA_PATH

    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    assert (
        payload["_meta"]["source_workbook"]
        == "https://www.bdew.de/energie/standardlastprofile-strom/"
    )


def test_annual_total_matches_annual_use() -> None:
    total = 0.0
    day = date(2026, 1, 1)
    while day.year == 2026:
        total += sum(h.kwh for h in baseline_day(day, 3500.0))
        day += timedelta(days=1)
    assert 0.99 * 3500.0 < total < 1.01 * 3500.0
