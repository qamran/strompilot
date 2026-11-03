"""Tests for the SMARD response parser."""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from strompilot.prices.models import berlin_day_bounds
from strompilot.prices.smard import (
    fetch_smard,
    parse_smard,
    select_week_file,
    week_timestamps,
)

FIXTURE = Path(__file__).parent / "fixtures" / "smard_4169.json"
INDEX_FIXTURE = Path(__file__).parent / "fixtures" / "smard_index.json"


def test_fixture_parses_and_skips_nulls() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    first_ts = payload["series"][0][0]
    berlin = ZoneInfo("Europe/Berlin")
    target = datetime.fromtimestamp(first_ts / 1000, tz=UTC).astimezone(berlin).date()
    points = parse_smard(payload, target)
    next_day = target + timedelta(days=1)
    day_start = datetime(target.year, target.month, target.day, tzinfo=berlin)
    day_end = datetime(next_day.year, next_day.month, next_day.day, tzinfo=berlin)
    expected = [
        row
        for row in payload["series"]
        if row[1] is not None
        and datetime.fromtimestamp(row[0] / 1000, tz=UTC) < day_end
        and datetime.fromtimestamp(row[0] / 1000, tz=UTC) + timedelta(hours=1)
        > day_start
    ]
    assert len(points) == len(expected)
    assert len(points) > 0
    assert points[0].eur_per_mwh == 23.88
    assert all(p.end - p.start == timedelta(hours=1) for p in points)


def load_index() -> list[int]:
    payload = json.loads(INDEX_FIXTURE.read_text(encoding="utf-8"))
    return week_timestamps(payload)


def test_week_timestamps_reads_index_fixture() -> None:
    stamps = load_index()
    assert len(stamps) > 400
    assert stamps == sorted(stamps)


def test_select_week_file_contains_target() -> None:
    stamps = load_index()
    latest = datetime.fromtimestamp(max(stamps) / 1000, tz=UTC)
    target = (latest + timedelta(days=2)).astimezone(ZoneInfo("Europe/Berlin")).date()
    chosen = select_week_file(stamps, target)
    target_ms = int(berlin_day_bounds(target)[0].timestamp() * 1000)
    assert chosen <= target_ms < chosen + 7 * 24 * 3600 * 1000


def test_select_week_file_clamps_out_of_range_targets() -> None:
    stamps = load_index()
    assert select_week_file(stamps, date(2027, 6, 1)) == max(stamps)
    assert select_week_file(stamps, date(2010, 1, 1)) == min(stamps)


def test_fetch_uses_short_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    seen: list[object] = []

    class _Response:
        def __init__(self, payload: object) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> object:
            return self._payload

    def fake_get(url: str, timeout: object) -> _Response:
        seen.append(timeout)
        if url.endswith("index_hour.json"):
            return _Response({"timestamps": [0]})
        return _Response({"series": []})

    monkeypatch.setattr(httpx, "get", fake_get)
    assert fetch_smard(date(2026, 1, 15)) == []
    assert seen == [5.0, 5.0]
