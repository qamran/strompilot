"""Price feed data models."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from pydantic import BaseModel


class PricePoint(BaseModel):
    """One priced interval in UTC."""

    start: datetime
    end: datetime
    eur_per_mwh: float

    @property
    def ct_per_kwh(self) -> float:
        """Household unit: 1 EUR/MWh equals 0.1 ct/kWh."""
        return round(self.eur_per_mwh / 10, 2)


class PriceSeries(BaseModel):
    """One day of prices with its source label."""

    date: date
    source: str
    stale: bool = False
    unit: str = "Eur/MWh"
    attribution: str
    prices: list[PricePoint]


BERLIN = ZoneInfo("Europe/Berlin")


def berlin_day_bounds(target: date) -> tuple[datetime, datetime]:
    """Return the UTC instants bounding a Berlin calendar day."""
    start = datetime(target.year, target.month, target.day, tzinfo=BERLIN)
    next_day = target + timedelta(days=1)
    end = datetime(next_day.year, next_day.month, next_day.day, tzinfo=BERLIN)
    return (start.astimezone(UTC), end.astimezone(UTC))
