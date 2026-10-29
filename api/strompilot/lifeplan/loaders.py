"""Price bar loader: day-ahead energy plus tariff levies, all-in."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from strompilot.lifeplan.schemas import PriceBar
from strompilot.prices.models import BERLIN, PricePoint
from strompilot.prices.service import Fetcher, get_day_ahead_prices
from strompilot.tariff.defaults import TariffDefaults
from strompilot.tariff.engine import decompose


@dataclass(frozen=True)
class LoadedPrices:
    """All-in hourly bars with the series source label."""

    bars: list[PriceBar]
    source: str
    stale: bool
    attribution: str


PriceLoader = Callable[[], LoadedPrices]


def load_price_bars(
    target: date,
    cache_dir: Path,
    now: datetime,
    defaults: TariffDefaults,
    awattar_fetcher: Fetcher | None = None,
    smard_fetcher: Fetcher | None = None,
) -> LoadedPrices:
    """Load one day of all-in hourly bars for the optimizer."""
    series = get_day_ahead_prices(
        target,
        cache_dir,
        now,
        awattar_fetcher=awattar_fetcher,
        smard_fetcher=smard_fetcher,
    )
    bars = [_to_bar(point, series.source, defaults) for point in series.prices]
    return LoadedPrices(
        bars=bars,
        source=series.source,
        stale=series.stale,
        attribution=series.attribution,
    )


def _to_bar(point: PricePoint, source: str, defaults: TariffDefaults) -> PriceBar:
    """Convert one energy point into an all-in Berlin-hour bar."""
    hour = point.start.astimezone(BERLIN).hour
    total = decompose(point.eur_per_mwh, defaults).total
    return PriceBar(hour=hour, price_ct_kwh=total, source=source)
