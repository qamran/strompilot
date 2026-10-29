"""H25 household baseline from the 2025 BDEW profiles."""

import json
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from strompilot.prices.models import BERLIN, berlin_day_bounds

DATA_PATH = Path(__file__).parent / "data" / "h25_2025.json"
NORMALIZATION_KWH = 1_000_000.0


class H25Data(BaseModel):
    """Twelve months of SA/FT/WT quarter-hour series."""

    months: dict[str, dict[str, list[float]]]


class HourlyBaseline(BaseModel):
    """One baseline hour in UTC with its household kWh."""

    start: datetime
    end: datetime
    kwh: float


@lru_cache(maxsize=1)
def load_h25() -> H25Data:
    """Load the distilled H25 data file, cached for the process."""
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return H25Data(months=payload["months"])


def day_type(target: date) -> str:
    """Map a date to its H25 day type.

    Sundays map to FT; state public holidays are not modeled yet and
    fall on their weekday type.
    """
    if target.weekday() == 5:
        return "SA"
    if target.weekday() == 6:
        return "FT"
    return "WT"


def baseline_day(target: date, annual_kwh: float) -> list[HourlyBaseline]:
    """Spread annual use over one Berlin day following the H25 shape."""
    series = load_h25().months[str(target.month)][day_type(target)]
    day_start, day_end = berlin_day_bounds(target)
    hours: list[HourlyBaseline] = []
    cursor = day_start
    while cursor < day_end:
        local_hour = cursor.astimezone(BERLIN).hour
        quarters = series[local_hour * 4 : local_hour * 4 + 4]
        kwh = annual_kwh * sum(quarters) / NORMALIZATION_KWH
        hours.append(
            HourlyBaseline(start=cursor, end=cursor + timedelta(hours=1), kwh=kwh)
        )
        cursor += timedelta(hours=1)
    return hours
