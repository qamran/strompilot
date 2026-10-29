"""Strompilot FastAPI application."""

import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from strompilot.contract import CONTRACT_VERSION, HealthResponse
from strompilot.memory.models import Episode, MemoryError, Preference
from strompilot.memory.store import MemoryStore
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


class PreferencesResponse(BaseModel):
    """Every preference of one household, keyed by name."""

    household_id: str
    preferences: dict[str, Any]


class EpisodesResponse(BaseModel):
    """One household's memories, newest first."""

    household_id: str
    episodes: list[Episode]


class SetPreferenceBody(BaseModel):
    """Preference value envelope, any JSON value."""

    value: Any


class AddEpisodeBody(BaseModel):
    """New memory envelope."""

    kind: str
    text: str


def _memory_db() -> Path:
    """Return the memory database path, honoring MEMORY_DB."""
    override = os.environ.get("MEMORY_DB")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent.parent / "data" / "memory.db"


def _store() -> MemoryStore:
    """Open the household memory store."""
    return MemoryStore(_memory_db())


@app.get("/memory/preferences", response_model=PreferencesResponse)
def read_preferences(household_id: str) -> PreferencesResponse:
    """List every preference of one household."""
    try:
        preferences = _store().list_preferences(household_id)
    except MemoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return PreferencesResponse(
        household_id=household_id,
        preferences={pref.key: pref.value for pref in preferences},
    )


@app.put("/memory/preferences/{key}", response_model=Preference)
def write_preference(
    key: str, household_id: str, body: SetPreferenceBody
) -> Preference:
    """Create or overwrite one preference."""
    try:
        return _store().set_preference(household_id, key, body.value)
    except MemoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.delete("/memory/preferences/{key}")
def remove_preference(key: str, household_id: str) -> dict[str, bool]:
    """Delete one preference, or 404 when it never existed."""
    try:
        deleted = _store().delete_preference(household_id, key)
    except MemoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="preference not found")
    return {"deleted": True}


@app.get("/memory/history", response_model=EpisodesResponse)
def read_history(
    household_id: str,
    kind: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> EpisodesResponse:
    """List one household's memories, newest first."""
    try:
        episodes = _store().list_episodes(household_id, kind=kind, limit=limit)
    except MemoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return EpisodesResponse(household_id=household_id, episodes=episodes)


@app.post("/memory/history", response_model=Episode)
def append_history(household_id: str, body: AddEpisodeBody) -> Episode:
    """Append one timestamped memory."""
    try:
        return _store().add_episode(household_id, body.kind, body.text)
    except MemoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.delete("/memory/history/{episode_id}")
def remove_episode(episode_id: int, household_id: str) -> dict[str, bool]:
    """Delete one memory of one household, or 404."""
    try:
        deleted = _store().delete_episode(household_id, episode_id)
    except MemoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="episode not found")
    return {"deleted": True}


@app.delete("/memory/household")
def forget_household(household_id: str) -> dict[str, bool]:
    """Delete every preference and memory of one household."""
    try:
        _store().forget_household(household_id)
    except MemoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"forgotten": True}
