"""SMARD day-ahead client (filter 4169, region DE-LU, hourly)."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from strompilot.prices.models import PricePoint, berlin_day_bounds

BASE_URL = "https://www.smard.de/app/chart_data/4169/DE-LU"
TIMEOUT_SECONDS = 30.0


def parse_smard(payload: dict[str, Any], target: date) -> list[PricePoint]:
    """Parse a SMARD week file into the non-null points of one Berlin day."""
    day_start, day_end = berlin_day_bounds(target)
    points: list[PricePoint] = []
    for row in payload.get("series", []):
        value = row[1]
        if value is None:
            continue
        start = datetime.fromtimestamp(row[0] / 1000, tz=UTC)
        end = start + timedelta(hours=1)
        if end > day_start and start < day_end:
            points.append(PricePoint(start=start, end=end, eur_per_mwh=float(value)))
    return sorted(points, key=lambda point: point.start)


def week_timestamps(index_payload: dict[str, Any]) -> list[int]:
    """Read week-file timestamps from the SMARD index payload."""
    raw = index_payload.get("timestamps", [])
    stamps = [int(value) for value in raw]
    if not stamps:
        raise ValueError(f"SMARD index keys: {sorted(index_payload.keys())}")
    return stamps


def select_week_file(stamps: list[int], target: date) -> int:
    """Select the week file containing a Berlin day, clamped to range."""
    day_start_ms = int(berlin_day_bounds(target)[0].timestamp() * 1000)
    past = [stamp for stamp in stamps if stamp <= day_start_ms]
    if past:
        return max(past)
    return min(stamps)


def fetch_smard(target: date) -> list[PricePoint]:
    """Fetch one Berlin day of German day-ahead prices from SMARD."""
    index_response = httpx.get(f"{BASE_URL}/index_hour.json", timeout=TIMEOUT_SECONDS)
    index_response.raise_for_status()
    stamps = week_timestamps(index_response.json())
    week_ts = select_week_file(stamps, target)
    url = f"{BASE_URL}/4169_DE-LU_hour_{week_ts}.json"
    response = httpx.get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return parse_smard(response.json(), target)
