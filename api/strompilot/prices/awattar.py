"""aWATTar day-ahead client on the German endpoint."""

from datetime import UTC, date, datetime
from typing import Any

import httpx

from strompilot.prices.models import PricePoint, berlin_day_bounds

BASE_URL = "https://api.awattar.de/v1/marketdata"
TIMEOUT_SECONDS = 30.0


def parse_awattar(payload: dict[str, Any], target: date) -> list[PricePoint]:
    """Parse an aWATTar marketdata payload into the points of one Berlin day."""
    day_start, day_end = berlin_day_bounds(target)
    points: list[PricePoint] = []
    for item in payload.get("data", []):
        if item.get("unit") != "Eur/MWh":
            raise ValueError(f"unsupported aWATTar unit: {item.get('unit')!r}")
        start = datetime.fromtimestamp(item["start_timestamp"] / 1000, tz=UTC)
        end = datetime.fromtimestamp(item["end_timestamp"] / 1000, tz=UTC)
        if end > day_start and start < day_end:
            points.append(
                PricePoint(start=start, end=end, eur_per_mwh=float(item["marketprice"]))
            )
    return sorted(points, key=lambda point: point.start)


def fetch_awattar(target: date) -> list[PricePoint]:
    """Fetch one Berlin day of German day-ahead prices from aWATTar."""
    day_start, day_end = berlin_day_bounds(target)
    start_ms = int(day_start.timestamp() * 1000)
    end_ms = int(day_end.timestamp() * 1000)
    url = f"{BASE_URL}?start={start_ms}&end={end_ms}"
    response = httpx.get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return parse_awattar(response.json(), target)
