"""Strompilot FastAPI application."""

import base64
import hashlib
import logging
import os
import re
import sqlite3
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from pydantic import BaseModel

from strompilot.agents.router import ModelRouter
from strompilot.agents.state import PlanState
from strompilot.agents.supervisor import build_graph
from strompilot.auth.mail import LogMailer, Mailer, mailer_from_env
from strompilot.auth.models import AuthError, Session
from strompilot.auth.store import AuthStore
from strompilot.contract import CONTRACT_VERSION, HealthResponse
from strompilot.flexalarm.loop import run_once
from strompilot.flexalarm.models import Alert, WatchReport
from strompilot.flexalarm.store import AlertStore
from strompilot.learning.models import Feedback, LearningError, Verdict
from strompilot.learning.update import LEARNED_KEY, update_from_feedback
from strompilot.lifeplan.loaders import PriceLoader, load_price_bars
from strompilot.lifeplan.schemas import DeviceConstraint, PriceBar
from strompilot.llm.types import ChatRouter, LlmError
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
from strompilot.report.images import ImageClient
from strompilot.report.monthly import MonthlyReport, art_prompt, build_month
from strompilot.tariff.defaults import DEFAULTS
from strompilot.wallbox.client import (
    WallboxClient,
    WallboxDriver,
    WallboxError,
    WallboxStatus,
    iso_window,
)
from strompilot.wallbox.policy import ChargePolicy, authorize

load_dotenv()

logger = logging.getLogger(__name__)

app = FastAPI(title="Strompilot API", version="0.1.0")

# The browser Leitstand reads the API cross-origin (web port vs API
# port), so the local frontend origins are allowed explicitly. Nothing
# else gets CORS headers. Credentials stay on so the session cookie
# travels; hosted deployments narrow the origins again.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:3100",
        "http://localhost:3100",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def read_health() -> HealthResponse:
    """Report that the API is up and which contract version it speaks."""
    return HealthResponse(
        status="ok",
        service="strompilot-api",
        contract_version=CONTRACT_VERSION,
    )


SESSION_COOKIE = "sp_session"

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _auth_store() -> AuthStore:
    """Open the auth store on the household database."""
    return AuthStore(_memory_db())


def _web_url() -> str:
    """Return the frontend base URL, honoring STROMPILOT_WEB_URL."""
    return os.environ.get("STROMPILOT_WEB_URL", "http://127.0.0.1:3100").rstrip("/")


def _mailer() -> Mailer:
    """Select the magic-link mailer from the environment."""
    return mailer_from_env()


def current_session(request: Request) -> Session:
    """Load the request's session from its cookie, or answer 401."""
    raw = request.cookies.get(SESSION_COOKIE, "")
    try:
        return _auth_store().load_session(raw)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _guard(session: Session, claimed: str) -> str:
    """Accept one claimed household only when it matches the session."""
    if not claimed.strip():
        raise HTTPException(status_code=422, detail="household_id must not be blank")
    if claimed != session.household_id:
        raise HTTPException(
            status_code=403, detail="household does not match the session"
        )
    return session.household_id


def _set_session_cookie(response: Response, raw: str) -> None:
    """Store one session token in a hardened cookie."""
    response.set_cookie(
        SESSION_COOKIE,
        raw,
        max_age=30 * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=os.environ.get("STROMPILOT_COOKIE_SECURE", "0") == "1",
        path="/",
    )


class RequestLinkBody(BaseModel):
    """One magic-link request for one email address."""

    email: str


class RequestLinkResponse(BaseModel):
    """Magic-link receipt; dev_link exists in log mode only."""

    email: str
    sent: bool
    dev_link: str | None = None


class SessionResponse(BaseModel):
    """One signed-in household with its session expiry."""

    email: str
    household_id: str
    expires_at: str


class SignOutResponse(BaseModel):
    """Sign-out receipt."""

    signed_out: bool


class MigrateBody(BaseModel):
    """Migrate one legacy local household into the signed-in account."""

    from_household: str


class MigrateResponse(BaseModel):
    """Migration receipt with per-table row counts."""

    household_id: str
    migrated: dict[str, int]


@app.post("/auth/request-link", response_model=RequestLinkResponse)
def request_link(body: RequestLinkBody) -> RequestLinkResponse:
    """Send one magic link to one email address."""
    email = body.email.strip().lower()
    if _EMAIL_RE.match(email) is None:
        raise HTTPException(status_code=422, detail="email must be valid")
    try:
        raw = _auth_store().issue_token(email)
    except AuthError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    link = f"{_web_url()}/auth/verify?token={raw}"
    mailer = _mailer()
    mailer.send(email, link)
    return RequestLinkResponse(
        email=email,
        sent=True,
        dev_link=link if isinstance(mailer, LogMailer) else None,
    )


@app.get("/auth/verify", response_model=SessionResponse)
def verify_link(token: str, response: Response) -> SessionResponse:
    """Redeem one magic link for a session cookie."""
    try:
        email = _auth_store().consume_token(token)
        raw = _auth_store().create_session(email)
        session = _auth_store().load_session(raw)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    _set_session_cookie(response, raw)
    return SessionResponse(
        email=session.email,
        household_id=session.household_id,
        expires_at=session.expires_at.isoformat(),
    )


@app.get("/auth/me", response_model=SessionResponse)
def read_me(session: Session = Depends(current_session)) -> SessionResponse:
    """Report the signed-in household."""
    return SessionResponse(
        email=session.email,
        household_id=session.household_id,
        expires_at=session.expires_at.isoformat(),
    )


@app.post("/auth/sign-out", response_model=SignOutResponse)
def sign_out(request: Request, response: Response) -> SignOutResponse:
    """Revoke the request's session and clear its cookie."""
    raw = request.cookies.get(SESSION_COOKIE, "")
    if raw:
        _auth_store().revoke_session(raw)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return SignOutResponse(signed_out=True)


@app.post("/auth/migrate", response_model=MigrateResponse)
def migrate_household(
    body: MigrateBody, session: Session = Depends(current_session)
) -> MigrateResponse:
    """Copy one legacy local household into the signed-in account."""
    source = body.from_household.strip()
    if not source:
        raise HTTPException(status_code=422, detail="from_household required")
    if source == session.household_id:
        raise HTTPException(status_code=422, detail="households must differ")
    memory = _store()
    meter = MeterStore(_memory_db())
    alerts = AlertStore(_memory_db())
    if not (
        memory.has_data(source) or meter.has_data(source) or alerts.has_data(source)
    ):
        raise HTTPException(status_code=404, detail="source household is empty")
    if (
        memory.has_data(session.household_id)
        or meter.has_data(session.household_id)
        or alerts.has_data(session.household_id)
    ):
        raise HTTPException(status_code=409, detail="account already has data")
    copied = memory.copy_household(source, session.household_id)
    copied["readings"] = meter.copy_household(source, session.household_id)
    copied["alerts"] = alerts.copy_household(source, session.household_id)
    return MigrateResponse(household_id=session.household_id, migrated=copied)


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
def read_preferences(
    household_id: str, session: Session = Depends(current_session)
) -> PreferencesResponse:
    """List every preference of one household."""
    household_id = _guard(session, household_id)
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
    key: str,
    household_id: str,
    body: SetPreferenceBody,
    session: Session = Depends(current_session),
) -> Preference:
    """Create or overwrite one preference."""
    household_id = _guard(session, household_id)
    try:
        return _store().set_preference(household_id, key, body.value)
    except MemoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.delete("/memory/preferences/{key}")
def remove_preference(
    key: str, household_id: str, session: Session = Depends(current_session)
) -> dict[str, bool]:
    """Delete one preference, or 404 when it never existed."""
    household_id = _guard(session, household_id)
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
    session: Session = Depends(current_session),
) -> EpisodesResponse:
    """List one household's memories, newest first."""
    household_id = _guard(session, household_id)
    try:
        episodes = _store().list_episodes(household_id, kind=kind, limit=limit)
    except MemoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return EpisodesResponse(household_id=household_id, episodes=episodes)


@app.post("/memory/history", response_model=Episode)
def append_history(
    household_id: str,
    body: AddEpisodeBody,
    session: Session = Depends(current_session),
) -> Episode:
    """Append one timestamped memory."""
    household_id = _guard(session, household_id)
    try:
        return _store().add_episode(household_id, body.kind, body.text)
    except MemoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.delete("/memory/history/{episode_id}")
def remove_episode(
    episode_id: int, household_id: str, session: Session = Depends(current_session)
) -> dict[str, bool]:
    """Delete one memory of one household, or 404."""
    household_id = _guard(session, household_id)
    try:
        deleted = _store().delete_episode(household_id, episode_id)
    except MemoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="episode not found")
    return {"deleted": True}


@app.delete("/memory/household")
def forget_household(
    household_id: str, session: Session = Depends(current_session)
) -> dict[str, bool]:
    """Delete every preference and memory of one household."""
    household_id = _guard(session, household_id)
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
    owner: str | None = None,
) -> ApprovalStatus:
    """Derive one thread's approval status from its checkpoint."""
    state = graph.get_state(_thread_config(thread_id))
    if not state.values:
        raise HTTPException(status_code=404, detail="thread not found")
    if owner is not None and state.values.get("household_id") != owner:
        raise HTTPException(status_code=403, detail="thread belongs elsewhere")
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
    session: Session = Depends(current_session),
) -> ApprovalStatus:
    """Report one thread's approval state."""
    return _read_status(thread_id, graph, session.household_id)


@app.post("/approvals/threads/{thread_id}/decide", response_model=ApprovalStatus)
def decide_thread(
    thread_id: str,
    body: DecisionBody,
    graph: CompiledStateGraph[PlanState, None, PlanState, PlanState] = Depends(
        get_approval_graph
    ),
    session: Session = Depends(current_session),
) -> ApprovalStatus:
    """Resume one paused thread with a human decision."""
    current = _read_status(thread_id, graph, session.household_id)
    if current.status != "paused":
        raise HTTPException(status_code=409, detail="thread is not awaiting approval")
    graph.invoke(
        Command(resume={"approved": body.approved}),
        _thread_config(thread_id),
    )
    return _read_status(thread_id, graph, session.household_id)


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
    lang: Literal["de", "en"] = "de",
    router: ModelRouter = Depends(get_watch_router),
    session: Session = Depends(current_session),
) -> WatchReport:
    """Run one watcher pass over one household and price day."""
    household_id = _guard(session, household_id)
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
            lang=lang,
        )
    except MemoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/flexalarm/alerts", response_model=AlertsResponse)
def read_alerts(
    household_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(current_session),
) -> AlertsResponse:
    """List one household's alerts, oldest first."""
    household_id = _guard(session, household_id)
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
    lang: Literal["de", "en"] = "de"


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
    keep_photo: bool = False,
    vision: MeterVision = Depends(get_meter_vision),
    session: Session = Depends(current_session),
) -> MeterReading:
    """Read one meter photo into a proposed reading.

    Photos are processed in memory and never stored unless keep_photo
    is set with explicit household consent.
    """
    household_id = _guard(session, household_id)
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
    photo_name = ""
    if keep_photo:
        photos = _photos_dir()
        photos.mkdir(parents=True, exist_ok=True)
        photo_path = photos / f"{uuid.uuid4().hex}.{extension}"
        photo_path.write_bytes(photo)
        photo_name = photo_path.name
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
            photo_path=photo_name,
            serial=proposal.serial,
        )
    except MeterError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return reading


@app.get("/meter/readings/{reading_id}/photo")
def read_reading_photo(
    reading_id: int,
    household_id: str,
    session: Session = Depends(current_session),
) -> FileResponse:
    """Serve one stored meter photo, kept only under explicit consent."""
    household_id = _guard(session, household_id)
    try:
        reading = MeterStore(_memory_db()).get(household_id, reading_id)
    except MeterError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if reading is None or not reading.photo_path:
        raise HTTPException(status_code=404, detail="photo not stored")
    photo = _photos_dir() / Path(reading.photo_path).name
    if not photo.is_file():
        raise HTTPException(status_code=404, detail="photo not stored")
    mime = next(
        (
            kind
            for kind, extension in _METER_MIME_EXTENSIONS.items()
            if photo.suffix.lower() == f".{extension}"
        ),
        "application/octet-stream",
    )
    return FileResponse(photo, media_type=mime)


@app.get("/meter/readings", response_model=ReadingsResponse)
def read_readings(
    household_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(current_session),
) -> ReadingsResponse:
    """List one household's meter readings, oldest first."""
    household_id = _guard(session, household_id)
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
    session: Session = Depends(current_session),
) -> ConfirmResponse:
    """Confirm one reading and show the re-plan diff, if any."""
    household_id = _guard(session, household_id)
    store = MeterStore(_memory_db())
    memory = _store()
    try:
        stored = store.confirm(household_id, reading_id, body.corrected_value_kwh)
    except MeterError as exc:
        status = 404 if "not found" in str(exc) else 422
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    reading = stored.model_copy(update={"photo_path": Path(stored.photo_path).name})
    calibration = calibrate(store.confirmed(household_id))
    english = body.lang == "en"
    if calibration is None:
        note = (
            "No yearly comparison yet: one more confirmed reading calibrates the usage."
            if english
            else "Noch kein Jahresvergleich möglich: Ein weiterer "
            "bestätigter Zählerstand kalibriert den Verbrauch."
        )
        return ConfirmResponse(
            reading=reading,
            calibration=None,
            diff=None,
            note=note,
        )
    old_annual = _annual_pref(memory, household_id)
    memory.set_preference(household_id, "annual_kwh", calibration.annual_kwh)
    if not body.devices:
        note = (
            "Annual use calibrated, no device plan passed for comparison."
            if english
            else "Jahresverbrauch kalibriert, kein Geräteplan zum Vergleich übergeben."
        )
        return ConfirmResponse(
            reading=reading,
            calibration=calibration,
            diff=None,
            note=note,
        )
    now = datetime.now(BERLIN)
    target = body.target_date or now.date() + timedelta(days=1)
    bars = load_price_bars(target, _cache_dir(), datetime.now(UTC), DEFAULTS).bars
    before = day_plan_totals(body.devices, bars, old_annual, target)
    after = day_plan_totals(body.devices, bars, calibration.annual_kwh, target)
    diff = diff_totals(before, after, body.lang)
    return ConfirmResponse(
        reading=reading, calibration=calibration, diff=diff, note=diff.note
    )


class FeedbackBody(BaseModel):
    """One household verdict on a planned device run."""

    device: str
    verdict: Verdict
    note: str = ""


class FeedbackResponse(BaseModel):
    """Stored feedback plus the learned windows it produced."""

    household_id: str
    episode: Episode
    learned_windows: dict[str, dict[str, int]]


class FeedbackListResponse(BaseModel):
    """One household's feedback, newest first."""

    household_id: str
    feedback: list[Episode]


@app.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(
    household_id: str,
    body: FeedbackBody,
    session: Session = Depends(current_session),
) -> FeedbackResponse:
    """Store one verdict and fold it into the learned windows."""
    household_id = _guard(session, household_id)
    try:
        feedback = Feedback(device=body.device, verdict=body.verdict, note=body.note)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    store = _store()
    try:
        current = store.get_preference(household_id, LEARNED_KEY) or {}
        if not isinstance(current, dict):
            current = {}
        learned = update_from_feedback(feedback, current)
        store.set_preference(household_id, LEARNED_KEY, learned)
        text = f"{feedback.device}: {feedback.verdict}"
        if feedback.note.strip():
            text += f" ({feedback.note.strip()})"
        episode = store.add_episode(household_id, "feedback", text)
    except (MemoryError, LearningError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return FeedbackResponse(
        household_id=household_id, episode=episode, learned_windows=learned
    )


@app.get("/feedback", response_model=FeedbackListResponse)
def read_feedback(
    household_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(current_session),
) -> FeedbackListResponse:
    """List one household's feedback, newest first."""
    household_id = _guard(session, household_id)
    try:
        episodes = _store().list_episodes(household_id, kind="feedback", limit=limit)
    except MemoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return FeedbackListResponse(household_id=household_id, feedback=episodes)


class MonthlyReportResponse(BaseModel):
    """One monthly report plus its cached illustration, if any."""

    report: MonthlyReport
    illustration_data_url: str | None


class IllustrationResponse(BaseModel):
    """One report illustration with its cache state."""

    month: str
    illustration_data_url: str
    cached: bool


def get_image_client() -> ImageClient:
    """Build the production image client for one request."""
    meta_key = os.environ.get("META_API_KEY", "")
    if not meta_key:
        raise HTTPException(status_code=500, detail="model keys missing")
    return ImageClient(meta_key)


def _art_dir() -> Path:
    """Return the report art directory, honoring REPORT_ART_DIR."""
    override = os.environ.get("REPORT_ART_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent.parent / "data" / "report_art"


def _art_path(household_id: str, month: str) -> Path:
    """Return the cached art file, keyed by household hash."""
    digest = hashlib.sha1(household_id.encode("utf-8")).hexdigest()[:16]
    return _art_dir() / digest / f"{month}.png"


def _checked_month(month: str) -> tuple[int, int]:
    """Parse YYYY-MM, rejecting bad formats and future months."""
    match = re.match(r"^(19|20)\d\d-(0[1-9]|1[0-2])$", month)
    if match is None:
        raise HTTPException(status_code=422, detail="month must be YYYY-MM")
    today = datetime.now(BERLIN).date()
    if month > today.strftime("%Y-%m"):
        raise HTTPException(status_code=422, detail="month must not be future")
    return int(month[0:4]), int(month[5:7])


def _month_loader(day: date) -> tuple[list[PriceBar], bool]:
    """Load one day of all-in bars, flagging sample fallback."""
    loaded = load_price_bars(day, _cache_dir(), datetime.now(UTC), DEFAULTS)
    return loaded.bars, loaded.source == "sample"


@app.get("/report/monthly", response_model=MonthlyReportResponse)
def read_monthly_report(
    household_id: str,
    month: str,
    flat_ct_kwh: float = Query(default=40.0, gt=0),
    lang: Literal["de", "en"] = "de",
    session: Session = Depends(current_session),
) -> MonthlyReportResponse:
    """Build one month of priced background use with savings."""
    household_id = _guard(session, household_id)
    year, month_number = _checked_month(month)
    annual = _annual_pref(_store(), household_id)
    report = build_month(year, month_number, annual, _month_loader, flat_ct_kwh, lang)
    art = _art_path(household_id, month)
    illustration = None
    if art.exists():
        illustration = "data:image/png;base64," + base64.b64encode(
            art.read_bytes()
        ).decode("ascii")
    return MonthlyReportResponse(report=report, illustration_data_url=illustration)


@app.post("/report/monthly/illustration", response_model=IllustrationResponse)
def make_illustration(
    household_id: str,
    month: str,
    images: ImageClient = Depends(get_image_client),
    session: Session = Depends(current_session),
) -> IllustrationResponse:
    """Generate or return the cached cover art for one month."""
    household_id = _guard(session, household_id)
    _checked_month(month)
    art = _art_path(household_id, month)
    if art.exists():
        cached = True
    else:
        try:
            art.parent.mkdir(parents=True, exist_ok=True)
            art.write_bytes(images.generate(art_prompt(month)))
        except LlmError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        cached = False
    illustration = "data:image/png;base64," + base64.b64encode(art.read_bytes()).decode(
        "ascii"
    )
    return IllustrationResponse(
        month=month, illustration_data_url=illustration, cached=cached
    )


@dataclass(frozen=True)
class PlanRunner:
    """One request's planning deps: router, loader, stores, wallbox."""

    router: ChatRouter
    loader_for: Callable[[date], PriceLoader]
    threads_db: Path
    memory: MemoryStore
    wallbox: WallboxDriver


def record_run_error(
    threads_db: Path, thread_id: str, message: str, household_id: str = ""
) -> None:
    """Persist one background-run crash beside the checkpoints."""
    conn = sqlite3.connect(threads_db)
    try:
        with conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS run_errors "
                "(thread_id TEXT PRIMARY KEY, message TEXT NOT NULL)"
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(run_errors)")}
            if "household_id" not in columns:
                conn.execute(
                    "ALTER TABLE run_errors ADD COLUMN household_id TEXT NOT NULL"
                    " DEFAULT ''"
                )
            conn.execute(
                "INSERT OR REPLACE INTO run_errors"
                " (thread_id, message, household_id) VALUES (?, ?, ?)",
                (thread_id, message, household_id),
            )
    finally:
        conn.close()


def read_run_error(threads_db: Path, thread_id: str) -> str | None:
    """Read one recorded crash, or None when the run never crashed."""
    if not threads_db.exists():
        return None
    conn = sqlite3.connect(threads_db)
    try:
        row = conn.execute(
            "SELECT message FROM run_errors WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()
    return str(row[0]) if row else None


def read_run_owner(threads_db: Path, thread_id: str) -> str | None:
    """Read one recorded crash's household, or None when unknown."""
    if not threads_db.exists():
        return None
    conn = sqlite3.connect(threads_db)
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(run_errors)")}
        if "household_id" not in columns:
            return None
        row = conn.execute(
            "SELECT household_id FROM run_errors WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()
    return str(row[0]) if row and row[0] else None


def get_plan_runner() -> PlanRunner:
    """Build the production planning deps for one request."""
    meta_key = os.environ.get("META_API_KEY", "")
    baseten_key = os.environ.get("BASETEN_API_KEY", "")
    if not meta_key or not baseten_key:
        raise HTTPException(status_code=500, detail="model keys missing")
    cache_dir = _cache_dir()
    now = datetime.now(UTC)
    return PlanRunner(
        router=ModelRouter.from_keys(meta_key, baseten_key),
        loader_for=lambda day: partial(load_price_bars, day, cache_dir, now, DEFAULTS),
        threads_db=_threads_db(),
        memory=_store(),
        wallbox=WallboxClient(),
    )


class PlanBody(BaseModel):
    """One planning request from the UI."""

    household_id: str
    text: str
    plan_day: date | None = None
    lang: Literal["de", "en"] = "de"


class PlanCreated(BaseModel):
    """One accepted planning run."""

    thread_id: str
    status: str


class PlanDetail(BaseModel):
    """One thread's plan state for the UI."""

    thread_id: str
    status: str
    schedule: list[dict[str, Any]] | None = None
    narration: str | None = None
    citations: list[dict[str, Any]] | None = None
    total_cost_eur: float | None = None
    error: str | None = None
    audit: list[str] = []


def _run_plan_to_pause(
    runner: PlanRunner,
    thread_id: str,
    household_id: str,
    text: str,
    plan_day: date,
    lang: str = "de",
) -> None:
    """Run one thread to its approval pause, recording failures."""
    try:
        with SqliteSaver.from_conn_string(str(runner.threads_db)) as saver:
            graph = build_graph(
                runner.router,
                runner.loader_for(plan_day),
                checkpointer=saver,
                memory=runner.memory,
                wallbox=runner.wallbox,
            )
            graph.invoke(
                {
                    "request": text,
                    "household_id": household_id,
                    "plan_day": plan_day.isoformat(),
                    "approval": "pending",
                    "lang": lang,
                },
                _thread_config(thread_id),
            )
    except Exception as exc:
        record_run_error(runner.threads_db, thread_id, str(exc), household_id)
        logger.exception("plan run %s failed", thread_id)


@app.post("/plan", response_model=PlanCreated, status_code=202)
def start_plan(
    body: PlanBody,
    background: BackgroundTasks,
    runner: PlanRunner = Depends(get_plan_runner),
    session: Session = Depends(current_session),
) -> PlanCreated:
    """Start one planning run in the background."""
    household_id = _guard(session, body.household_id)
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="text must not be blank")
    thread_id = uuid.uuid4().hex
    plan_day = body.plan_day or datetime.now(BERLIN).date() + timedelta(days=1)
    background.add_task(
        _run_plan_to_pause,
        runner,
        thread_id,
        household_id,
        body.text,
        plan_day,
        body.lang,
    )
    return PlanCreated(thread_id=thread_id, status="running")


@app.get("/plan/{thread_id}", response_model=PlanDetail)
def read_plan(
    thread_id: str,
    runner: PlanRunner = Depends(get_plan_runner),
    session: Session = Depends(current_session),
) -> PlanDetail:
    """Read one thread's plan state."""
    recorded = read_run_error(runner.threads_db, thread_id)
    try:
        with SqliteSaver.from_conn_string(str(runner.threads_db)) as saver:
            snapshot = saver.get_tuple(_thread_config(thread_id))
            if snapshot is None:
                if recorded is None:
                    raise HTTPException(status_code=404, detail="unknown thread")
                owner = read_run_owner(runner.threads_db, thread_id)
                if owner != session.household_id:
                    raise HTTPException(
                        status_code=403, detail="thread belongs elsewhere"
                    )
                values: dict[str, Any] = {}
                status = "blocked"
            else:
                values = snapshot.checkpoint["channel_values"]
                if not isinstance(values, dict):
                    raise HTTPException(status_code=500, detail="unreadable thread")
                if values.get("household_id") != session.household_id:
                    raise HTTPException(
                        status_code=403, detail="thread belongs elsewhere"
                    )
                graph = build_graph(
                    runner.router,
                    runner.loader_for(datetime.now(BERLIN).date()),
                    checkpointer=saver,
                    memory=runner.memory,
                    wallbox=runner.wallbox,
                )
                status = _read_status(thread_id, graph).status
                if recorded is not None:
                    status = "blocked"
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=404, detail="unknown thread") from exc
    audit = values.get("audit", [])
    return PlanDetail(
        thread_id=thread_id,
        status=status,
        schedule=values.get("schedule"),
        narration=values.get("narration"),
        citations=values.get("citations"),
        total_cost_eur=values.get("total_cost_eur"),
        error=recorded if recorded is not None else values.get("error"),
        audit=[str(event) for event in audit] if isinstance(audit, list) else [],
    )


def _trace_events(thread_id: str, runner: PlanRunner) -> Iterator[str]:
    """Yield new audit lines until the thread settles or time runs out."""
    with SqliteSaver.from_conn_string(str(runner.threads_db)) as saver:
        graph = build_graph(
            runner.router,
            runner.loader_for(datetime.now(BERLIN).date()),
            checkpointer=saver,
            memory=runner.memory,
            wallbox=runner.wallbox,
        )
        seen = 0
        for _ in range(150):
            try:
                snapshot = graph.get_state(_thread_config(thread_id))
                status = _read_status(thread_id, graph).status
            except HTTPException:
                return
            values = snapshot.values if isinstance(snapshot.values, dict) else {}
            audit = values.get("audit", [])
            lines = [str(event) for event in audit] if isinstance(audit, list) else []
            for line in lines[seen:]:
                yield f"data: {line}\n\n"
            seen = len(lines)
            if status in ("published", "done", "blocked"):
                return
            time.sleep(0.4)


@app.get("/plan/{thread_id}/trace")
def stream_trace(
    thread_id: str,
    runner: PlanRunner = Depends(get_plan_runner),
    session: Session = Depends(current_session),
) -> StreamingResponse:
    """Stream one thread's audit trace as server-sent events."""
    try:
        with SqliteSaver.from_conn_string(str(runner.threads_db)) as saver:
            snapshot = saver.get_tuple(_thread_config(thread_id))
    except Exception as exc:
        raise HTTPException(status_code=404, detail="unknown thread") from exc
    if snapshot is None:
        raise HTTPException(status_code=404, detail="unknown thread")
    values = snapshot.checkpoint.get("channel_values")
    if not isinstance(values, dict) or values.get("household_id") != (
        session.household_id
    ):
        raise HTTPException(status_code=403, detail="thread belongs elsewhere")
    return StreamingResponse(
        _trace_events(thread_id, runner), media_type="text/event-stream"
    )


def get_wallbox_client() -> WallboxDriver:
    """Build the wallbox driver for one request (local simulator)."""
    return WallboxClient()


@app.get("/wallbox/status", response_model=WallboxStatus)
def read_wallbox_status(
    wallbox: WallboxDriver = Depends(get_wallbox_client),
) -> WallboxStatus:
    """Report the wallbox live status."""
    try:
        return wallbox.status()
    except WallboxError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


class ProgramBody(BaseModel):
    """One manual charge program from the UI."""

    day: date | None = None
    start: str
    end: str
    max_kw: float


@app.post("/wallbox/program", response_model=WallboxStatus)
def program_wallbox(
    body: ProgramBody,
    wallbox: WallboxDriver = Depends(get_wallbox_client),
) -> WallboxStatus:
    """Program one charge window behind the policy gates."""
    day = body.day or datetime.now(BERLIN).date()
    try:
        start_iso, end_iso = iso_window(day, body.start, body.end)
    except WallboxError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    decision = authorize(ChargePolicy(), start_iso, end_iso, body.max_kw)
    if not decision.allowed:
        raise HTTPException(status_code=422, detail=decision.reason)
    try:
        return wallbox.program(start_iso, end_iso, body.max_kw)
    except WallboxError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
