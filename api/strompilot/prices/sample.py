"""Deterministic labeled sample fallback for the price feed."""

import math
from datetime import date, timedelta

from strompilot.prices.models import (
    BERLIN,
    PricePoint,
    PriceSeries,
    berlin_day_bounds,
)

ATTRIBUTION = "Sample data for demo purposes - no live feed"


def sample_series(target: date) -> PriceSeries:
    """Build a fixed curve over one Berlin day so the demo never breaks."""
    day_start, day_end = berlin_day_bounds(target)
    prices: list[PricePoint] = []
    cursor = day_start
    while cursor < day_end:
        local_hour = cursor.astimezone(BERLIN)
        hour = local_hour.hour + local_hour.minute / 60
        value = 180 + 90 * math.sin(2 * math.pi * (hour - 9) / 24)
        if 17 <= hour < 21:
            value += 60
        prices.append(
            PricePoint(
                start=cursor,
                end=cursor + timedelta(hours=1),
                eur_per_mwh=round(value, 2),
            )
        )
        cursor += timedelta(hours=1)
    return PriceSeries(
        date=target, source="sample", attribution=ATTRIBUTION, prices=prices
    )
