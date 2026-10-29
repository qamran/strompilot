"""Strompilot FastAPI application."""

import os
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI

from strompilot.contract import CONTRACT_VERSION, HealthResponse
from strompilot.prices.models import PriceSeries
from strompilot.prices.service import get_day_ahead_prices

app = FastAPI(title="Strompilot API", version="0.1.0")


@app.get("/health", response_model=HealthResponse)
def read_health() -> HealthResponse:
    """Report that the API is up and which contract version it speaks."""
    return HealthResponse(
        status="ok",
        service="strompilot-api",
        contract_version=CONTRACT_VERSION,
    )


def _cache_dir() -> Path:
    """Return the price cache directory, honoring PRICE_CACHE_DIR."""
    override = os.environ.get("PRICE_CACHE_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent.parent / "data" / "prices"


@app.get("/prices/day-ahead", response_model=PriceSeries)
def read_day_ahead_prices(date: date | None = None) -> PriceSeries:
    """Return one day of day-ahead prices with its source label."""
    target = date or datetime.now(ZoneInfo("Europe/Berlin")).date()
    return get_day_ahead_prices(target, _cache_dir(), datetime.now(UTC))
