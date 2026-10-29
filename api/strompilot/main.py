"""Strompilot FastAPI application."""

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from pydantic import BaseModel

from strompilot.agents.router import ModelRouter
from strompilot.agents.state import PlanState
from strompilot.agents.supervisor import build_graph
from strompilot.contract import CONTRACT_VERSION, HealthResponse
from strompilot.flexalarm.loop import run_once
from strompilot.flexalarm.models import Alert, WatchReport
from strompilot.flexalarm.store import AlertStore
from strompilot.lifeplan.loaders import load_price_bars
from strompilot.lifeplan.schemas import DeviceConstraint
from strompilot.llm.types import LlmError
from strompilot.memory.models import Episode, MemoryError, Preference
from strompilot.memory.store import MemoryStore
from strompilot.metervision.calibrate import FALLBACK_ANNUAL_KWH, calibrate
from strompilot.metervision.models import (
    Calibration,
    MeterError,
    MeterReading,
    ReplanDiff,
)
from strompilot.metervision.pipeline import MeterVision, process_photo
from strompilot.metervision.replan import day_plan_totals, diff_totals
from strompilot.metervision.sam import SamClient
from strompilot.metervision.store import MeterStore
from strompilot.prices.models import BERLIN, PriceSeries
from strompilot.prices.service import get_day_ahead_prices
from strompilot.tariff.defaults import DEFAULTS

load_dotenv()

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


class ApprovalReview(BaseModel):
    """The paused plan awaiting a human decision."""

    type: str
    schedule: list[dict[str, Any]]
    total_cost_eur: float
    narration: str


class ApprovalStatus(BaseModel):
    """One thread's approval state with its review or outcome."""

    thread_id: str
    status: str
    published: bool = False
    review: ApprovalReview | None = None
    error: str | None = None


class DecisionBody(BaseModel):
    """Human approval decision."""

    approved: bool


def _threads_db() -> Path:
    """Return the thread database path, honoring THREADS_DB."""
    override = os.environ.get("THREADS_DB")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent.parent / "data" / "threads.db"


def get_approval_graph() -> Iterator[
    CompiledStateGraph[PlanState, None, PlanState, PlanState]
]:
    """Yield one checkpointed supervisor graph per request."""
    meta_key = os.environ.get("META_API_KEY", "")
    baseten_key = os.environ.get("BASETEN_API_KEY", "")
    if not meta_key or not baseten_key:
        raise HTTPException(status_code=500, detail="model keys missing")
    router = ModelRouter.from_keys(meta_key, baseten_key)
    now = datetime.now(BERLIN)
    loader = partial(
        load_price_bars,
        now.date() + timedelta(days=1),
        _cache_dir(),
        datetime.now(UTC),
        DEFAULTS,
    )
    with SqliteSaver.from_conn_string(str(_threads_db())) as saver:
        yield build_graph(router, loader, checkpointer=saver)


def _thread_config(thread_id: str) -> RunnableConfig:
    """Build the LangGraph config for one thread."""
    return {"configurable": {"thread_id": thread_id}}


def _read_status(
    thread_id: str,
    graph: CompiledStateGraph[PlanState, None, PlanState, PlanState],
) -> ApprovalStatus:
    """Derive one thread's approval status from its checkpoint."""
    state = graph.get_state(_thread_config(thread_id))
    if not state.values:
        raise HTTPException(status_code=404, detail="thread not found")
    for task in state.tasks:
        for found in task.interrupts:
            review = found.value
            return ApprovalStatus(
                thread_id=thread_id,
                status="paused",
                review=ApprovalReview(
                    type=str(review.get("type", "plan_approval")),
                    schedule=list(review.get("schedule", [])),
                    total_cost_eur=float(review.get("total_cost_eur", 0.0)),
                    narration=str(review.get("narration", "")),
                ),
            )
    values = state.values
    if values.get("published") is True:
        return ApprovalStatus(thread_id=thread_id, status="published", published=True)
    if values.get("error"):
        return ApprovalStatus(
            thread_id=thread_id, status="blocked", error=str(values["error"])
        )
    if not state.tasks:
        return ApprovalStatus(thread_id=thread_id, status="done")
    return ApprovalStatus(thread_id=thread_id, status="running")


@app.get("/approvals/threads/{thread_id}", response_model=ApprovalStatus)
def read_thread(
    thread_id: str,
    graph: CompiledStateGraph[PlanState, None, PlanState, PlanState] = Depends(
        get_approval_graph
    ),
) -> ApprovalStatus:
    """Report one thread's approval state."""
    return _read_status(thread_id, graph)


@app.post("/approvals/threads/{thread_id}/decide", response_model=ApprovalStatus)
def decide_thread(
    thread_id: str,
    body: DecisionBody,
    graph: CompiledStateGraph[PlanState, None, PlanState, PlanState] = Depends(
        get_approval_graph
    ),
) -> ApprovalStatus:
    """Resume one paused thread with a human decision."""
    current = _read_status(thread_id, graph)
    if current.status != "paused":
        raise HTTPException(status_code=409, detail="thread is not awaiting approval")
    graph.invoke(
        Command(resume={"approved": body.approved}),
        _thread_config(thread_id),
    )
    return _read_status(thread_id, graph)


class AlertsResponse(BaseModel):
    """One household's alerts, oldest first."""

    household_id: str
    alerts: list[Alert]


def get_watch_router() -> ModelRouter:
    """Build the production router for one watcher pass."""
    meta_key = os.environ.get("META_API_KEY", "")
    baseten_key = os.environ.get("BASETEN_API_KEY", "")
    if not meta_key or not baseten_key:
        raise HTTPException(status_code=500, detail="model keys missing")
    return ModelRouter.from_keys(meta_key, baseten_key)


@app.post("/flexalarm/watch", response_model=WatchReport)
def trigger_watch(
    household_id: str,
    date: date | None = None,
    router: ModelRouter = Depends(get_watch_router),
) -> WatchReport:
    """Run one watcher pass over one household and price day."""
    now = datetime.now(BERLIN)
    target = date or now.date() + timedelta(days=1)
    try:
        series = get_day_ahead_prices(target, _cache_dir(), datetime.now(UTC))
        return run_once(
            household_id=household_id,
            series=series,
            memory=_store(),
            alerts=AlertStore(_memory_db()),
            router=router,
            senders=None,
            now=now,
        )
    except MemoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/flexalarm/alerts", response_model=AlertsResponse)
def read_alerts(
    household_id: str,
    limit: int = Query(default=50, ge=1, le=200),
) -> AlertsResponse:
    """List one household's alerts, oldest first."""
    try:
        alerts = AlertStore(_memory_db()).list_alerts(household_id, limit=limit)
    except MemoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AlertsResponse(household_id=household_id, alerts=alerts)


class ReadingsResponse(BaseModel):
    """One household's meter readings, oldest first."""

    household_id: str
    readings: list[MeterReading]


class ConfirmBody(BaseModel):
    """Human confirmation with the re-plan context."""

    corrected_value_kwh: float | None = None
    target_date: date | None = None
    devices: list[DeviceConstraint] | None = None


class ConfirmResponse(BaseModel):
    """Confirmed reading plus calibration and re-plan diff, if any."""

    reading: MeterReading
    calibration: Calibration | None
    diff: ReplanDiff | None
    note: str


def get_meter_vision() -> MeterVision:
    """Build the production vision deps for one request."""
    meta_key = os.environ.get("META_API_KEY", "")
    baseten_key = os.environ.get("BASETEN_API_KEY", "")
    if not meta_key or not baseten_key:
        raise HTTPException(status_code=500, detail="model keys missing")
    return MeterVision(
        router=ModelRouter.from_keys(meta_key, baseten_key),
        sam=SamClient(meta_key),
    )


def _photos_dir() -> Path:
    """Return the meter photo directory, honoring METER_PHOTOS_DIR."""
    override = os.environ.get("METER_PHOTOS_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent.parent / "data" / "meter_photos"


_METER_MIME_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}
_MAX_PHOTO_BYTES = 10 * 1024 * 1024


@app.post("/meter/readings", response_model=MeterReading)
def propose_reading(
    household_id: str,
    file: UploadFile = File(...),
    vision: MeterVision = Depends(get_meter_vision),
) -> MeterReading:
    """Read one meter photo into a proposed reading."""
    if not household_id.strip():
        raise HTTPException(status_code=422, detail="household_id must not be blank")
    mime = file.content_type or ""
    extension = _METER_MIME_EXTENSIONS.get(mime)
    if extension is None:
        raise HTTPException(status_code=422, detail="photo must be an image")
    photo = file.file.read()
    if len(photo) > _MAX_PHOTO_BYTES:
        raise HTTPException(status_code=422, detail="photo exceeds 10 MB")
    try:
        proposal = process_photo(photo, mime, vision.sam, vision.router)
    except MeterError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LlmError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    photos = _photos_dir()
    photos.mkdir(parents=True, exist_ok=True)
    photo_path = photos / f"{uuid.uuid4().hex}.{extension}"
    photo_path.write_bytes(photo)
    try:
        reading = MeterStore(_memory_db()).propose(
            household_id=household_id,
            value_kwh=proposal.value_kwh,
            read_at=datetime.now(UTC),
            confidence=proposal.confidence,
            sam_box=(
                f"{proposal.sam_box.x1},{proposal.sam_box.y1},"
                f"{proposal.sam_box.x2},{proposal.sam_box.y2}"
                if proposal.sam_box
                else None
            ),
            photo_path=str(photo_path),
        )
    except MeterError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return reading.model_copy(update={"photo_path": photo_path.name})


@app.get("/meter/readings", response_model=ReadingsResponse)
def read_readings(
    household_id: str,
    limit: int = Query(default=50, ge=1, le=200),
) -> ReadingsResponse:
    """List one household's meter readings, oldest first."""
    try:
        readings = MeterStore(_memory_db()).list_readings(household_id, limit=limit)
    except MeterError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    public = [
        reading.model_copy(update={"photo_path": Path(reading.photo_path).name})
        for reading in readings
    ]
    return ReadingsResponse(household_id=household_id, readings=public)


def _annual_pref(memory: MemoryStore, household_id: str) -> float:
    """Read the calibrated annual use, or the fallback before proof."""
    value = memory.get_preference(household_id, "annual_kwh")
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    return FALLBACK_ANNUAL_KWH


@app.post("/meter/readings/{reading_id}/confirm", response_model=ConfirmResponse)
def confirm_reading(
    reading_id: int,
    household_id: str,
    body: ConfirmBody,
) -> ConfirmResponse:
    """Confirm one reading and show the re-plan diff, if any."""
    store = MeterStore(_memory_db())
    memory = _store()
    try:
        stored = store.confirm(household_id, reading_id, body.corrected_value_kwh)
    except MeterError as exc:
        status = 404 if "not found" in str(exc) else 422
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    reading = stored.model_copy(update={"photo_path": Path(stored.photo_path).name})
    calibration = calibrate(store.confirmed(household_id))
    if calibration is None:
        return ConfirmResponse(
            reading=reading,
            calibration=None,
            diff=None,
            note="Noch kein Jahresvergleich möglich: Ein weiterer "
            "bestätigter Zählerstand kalibriert den Verbrauch.",
        )
    old_annual = _annual_pref(memory, household_id)
    memory.set_preference(household_id, "annual_kwh", calibration.annual_kwh)
    if not body.devices:
        return ConfirmResponse(
            reading=reading,
            calibration=calibration,
            diff=None,
            note="Jahresverbrauch kalibriert, kein Geräteplan zum Vergleich übergeben.",
        )
    now = datetime.now(BERLIN)
    target = body.target_date or now.date() + timedelta(days=1)
    bars = load_price_bars(target, _cache_dir(), datetime.now(UTC), DEFAULTS).bars
    before = day_plan_totals(body.devices, bars, old_annual, target)
    after = day_plan_totals(body.devices, bars, calibration.annual_kwh, target)
    diff = diff_totals(before, after)
    return ConfirmResponse(
        reading=reading, calibration=calibration, diff=diff, note=diff.note
    )
