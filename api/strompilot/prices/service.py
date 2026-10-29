"""Price service: fresh cache, live sources, stale cache, then sample."""

from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path

from strompilot.prices import awattar, smard
from strompilot.prices.cache import DiskCache
from strompilot.prices.models import BERLIN, PricePoint, PriceSeries
from strompilot.prices.sample import sample_series

AWATTAR_ATTRIBUTION = "EPEX Spot day-ahead prices via aWATTar"
SMARD_ATTRIBUTION = "Bundesnetzagentur | SMARD.de (CC BY 4.0)"
FRESHNESS = timedelta(hours=24)

Fetcher = Callable[[date], list[PricePoint]]


def get_day_ahead_prices(
    target: date,
    cache_dir: Path,
    now: datetime,
    awattar_fetcher: Fetcher | None = None,
    smard_fetcher: Fetcher | None = None,
) -> PriceSeries:
    """Return one day of prices, trying each source in fallback order."""
    live_awattar = awattar_fetcher or awattar.fetch_awattar
    live_smard = smard_fetcher or smard.fetch_smard
    today = now.astimezone(BERLIN).date()
    cache = DiskCache(cache_dir)
    entry = cache.read(target)
    if entry is not None and entry.fetched_at >= now - FRESHNESS:
        return entry.series
    for name, fetcher, attribution in (
        ("awattar", live_awattar, AWATTAR_ATTRIBUTION),
        ("smard", live_smard, SMARD_ATTRIBUTION),
    ):
        if cache.last_fetch(name) == today:
            continue
        try:
            points = fetcher(target)
        except Exception:
            continue
        if not points:
            continue
        cache.mark_fetched(name, today)
        series = PriceSeries(
            date=target,
            source=f"{name}-live",
            attribution=attribution,
            prices=points,
        )
        cache.write(target, series, f"{name}-live", now)
        return series
    if entry is not None:
        entry.series.stale = True
        return entry.series
    return sample_series(target)
