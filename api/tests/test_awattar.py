"""Tests for the aWATTar response parser."""

import json
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from strompilot.prices.awattar import parse_awattar

FIXTURE = Path(__file__).parent / "fixtures" / "awattar_de.json"
BERLIN = ZoneInfo("Europe/Berlin")


def test_fixture_parses_with_exact_first_point() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    first_ts = payload["data"][0]["start_timestamp"]
    target = datetime.fromtimestamp(first_ts / 1000, tz=UTC).astimezone(BERLIN).date()
    points = parse_awattar(payload, target)
    assert len(points) > 0
    first = points[0]
    assert first.start == datetime.fromtimestamp(1793221200000 / 1000, tz=UTC)
    assert first.eur_per_mwh == 258.28
    assert all(p.end > p.start for p in points)


def test_unknown_unit_is_rejected() -> None:
    payload = {
        "data": [
            {
                "start_timestamp": 1793221200000,
                "end_timestamp": 1793224800000,
                "marketprice": 10.0,
                "unit": "Cent/kWh",
            }
        ]
    }
    target = (
        datetime.fromtimestamp(1793221200000 / 1000, tz=UTC).astimezone(BERLIN).date()
    )
    with pytest.raises(ValueError, match="unit"):
        parse_awattar(payload, target)


def test_points_bucket_by_berlin_day() -> None:
    start = datetime(2026, 10, 29, 23, 15, tzinfo=UTC)
    end = datetime(2026, 10, 29, 23, 45, tzinfo=UTC)
    payload = {
        "data": [
            {
                "start_timestamp": int(start.timestamp() * 1000),
                "end_timestamp": int(end.timestamp() * 1000),
                "marketprice": 100.0,
                "unit": "Eur/MWh",
            }
        ]
    }
    assert parse_awattar(payload, date(2026, 10, 29)) == []
    assert len(parse_awattar(payload, date(2026, 10, 30))) == 1
