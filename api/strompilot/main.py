"""Strompilot FastAPI application."""

import base64
import hashlib
import io
import json
import logging
import os
import re
import shutil
import sqlite3
import time
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any, BinaryIO, Literal
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
from langgraph.checkpoint.base import CheckpointTuple
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field, model_validator

from strompilot.agents.router import ModelRouter
from strompilot.agents.state import PlanState
from strompilot.agents.supervisor import build_graph
from strompilot.auth.mail import Mailer, mailer_from_env
from strompilot.auth.models import AuthError, Session
from strompilot.auth.store import AuthStore
from strompilot.contract import CONTRACT_VERSION, HealthResponse
from strompilot.db import connect as db_connect
from strompilot.flexalarm.loop import run_once
from strompilot.flexalarm.models import Alert, WatchReport
from strompilot.flexalarm.store import AlertStore
from strompilot.learning.models import Feedback, LearningError, Verdict
from strompilot.learning.update import LEARNED_KEY, update_from_feedback
from strompilot.lifeplan.loaders import PriceLoader, load_price_bars
from strompilot.lifeplan.schemas import DeviceConstraint, PriceBar
from strompilot.llm.client import META_BASE_URL, SPARK_MODEL, ChatClient
from strompilot.llm.types import ChatRouter, LlmError, Message
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
from strompilot.retrieval.baseten import BasetenClient
from strompilot.retrieval.corpus import load_corpus
from strompilot.retrieval.retriever import Retriever
from strompilot.solar.estimate import estimate_roof
from strompilot.tariff.defaults import DEFAULTS
from strompilot.tariff.engine import decompose
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


def _prewarm_databases() -> None:
    """Create every table once at startup, before any request."""
    memory_db = _memory_db()
    MemoryStore(memory_db)
    MeterStore(memory_db)
    AlertStore(memory_db)
    AuthStore(memory_db)
    _ensure_run_tables(_threads_db())


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Prepare the databases, warn about dev links, then serve."""
    _prewarm_databases()
    if os.environ.get("STROMPILOT_DEV_LINKS") == "1":
        logger.warning(
            "STROMPILOT_DEV_LINKS=1: magic links are returned in API "
            "responses; never enable in production"
        )
    yield


app = FastAPI(title="Strompilot API", version="0.1.0", lifespan=lifespan)

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
    consent: bool = False


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
    consent_agreed: bool = False


CONSENT_KEY = "consent"


def _consent_agreed(household_id: str) -> bool:
    """Report whether one household agreed to power planning."""
    try:
        consent = _store().get_preference(household_id, CONSENT_KEY)
    except MemoryError:
        return False
    return isinstance(consent, dict) and consent.get("agreed") is True


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


_LINK_RATE_LIMIT = 50
_LINK_RATE_WINDOW_SECONDS = 60.0
_link_rate_hits: dict[str, list[float]] = {}


def reset_link_rate_limits() -> None:
    """Clear the request-link rate limiter (tests only)."""
    _link_rate_hits.clear()


def _check_link_rate_limit(client_ip: str) -> None:
    """Reject one request-link caller past 50 hits per minute."""
    now = time.time()
    hits = [
        hit
        for hit in _link_rate_hits.get(client_ip, [])
        if now - hit < _LINK_RATE_WINDOW_SECONDS
    ]
    if len(hits) >= _LINK_RATE_LIMIT:
        raise HTTPException(
            status_code=429, detail="too many link requests, retry in a minute"
        )
    hits.append(now)
    _link_rate_hits[client_ip] = hits


@app.post("/auth/request-link", response_model=RequestLinkResponse)
def request_link(body: RequestLinkBody, request: Request) -> RequestLinkResponse:
    """Send one magic link to one email address."""
    email = body.email.strip().lower()
    if _EMAIL_RE.match(email) is None:
        raise HTTPException(status_code=422, detail="email must be valid")
    client_ip = request.client.host if request.client else "unknown"
    _check_link_rate_limit(client_ip)
    try:
        raw = _auth_store().issue_token(email, consent_agreed=body.consent)
    except AuthError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    link = f"{_web_url()}/auth/verify?token={raw}"
    mailer = _mailer()
    mailer.send(email, link)
    dev_links = os.environ.get("STROMPILOT_DEV_LINKS") == "1"
    return RequestLinkResponse(
        email=email,
        sent=True,
        dev_link=link if dev_links else None,
    )


@app.get("/auth/verify", response_model=SessionResponse)
def verify_link(token: str, response: Response) -> SessionResponse:
    """Redeem one magic link for a session cookie."""
    try:
        email = _auth_store().consume_token(token)
        consent = _auth_store().read_token_consent(token)
        raw = _auth_store().create_session(email)
        session = _auth_store().load_session(raw)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if consent:
        _store().set_preference(
            session.household_id,
            CONSENT_KEY,
            {"agreed": True, "at": datetime.now(UTC).isoformat()},
        )
    _set_session_cookie(response, raw)
    return SessionResponse(
        email=session.email,
        household_id=session.household_id,
        expires_at=session.expires_at.isoformat(),
        consent_agreed=consent,
    )


@app.get("/auth/me", response_model=SessionResponse)
def read_me(session: Session = Depends(current_session)) -> SessionResponse:
    """Report the signed-in household."""
    return SessionResponse(
        email=session.email,
        household_id=session.household_id,
        expires_at=session.expires_at.isoformat(),
        consent_agreed=_consent_agreed(session.household_id),
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
    """Return one day of day-ahead prices with all-in household figures."""
    target = date or datetime.now(ZoneInfo("Europe/Berlin")).date()
    series = get_day_ahead_prices(target, _cache_dir(), datetime.now(UTC))
    for point in series.prices:
        if point.all_in_ct_kwh is None:
            point.all_in_ct_kwh = decompose(point.eur_per_mwh, DEFAULTS).total
    return series


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

    @model_validator(mode="after")
    def _cap_value(self) -> "SetPreferenceBody":
        """Cap the serialized value so one write cannot flood the store."""
        if len(json.dumps(self.value, default=str)) > 8000:
            raise ValueError("value must be at most 8000 characters")
        return self


class AddEpisodeBody(BaseModel):
    """New memory envelope."""

    kind: str
    text: str = Field(max_length=2000)


def _memory_db() -> Path:
    """Return the memory database path, honoring MEMORY_DB."""
    override = os.environ.get("MEMORY_DB")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent.parent / "data" / "memory.db"


def _store() -> MemoryStore:
    """Open the household memory store."""
    return MemoryStore(_memory_db())


@dataclass(frozen=True)
class Settings:
    """One request's configuration snapshot, read from the environment."""

    meta_key: str
    baseten_key: str
    threads_db: Path
    memory_db: Path

    @classmethod
    def from_env(cls) -> "Settings":
        """Build one snapshot from the current environment."""
        return cls(
            meta_key=os.environ.get("META_API_KEY", ""),
            baseten_key=os.environ.get("BASETEN_API_KEY", ""),
            threads_db=_threads_db(),
            memory_db=_memory_db(),
        )


def get_settings() -> Settings:
    """Build the settings snapshot for one request."""
    return Settings.from_env()


def require_model_keys(
    settings: Settings = Depends(get_settings),
) -> tuple[str, str]:
    """Require both model keys, returning them for one request."""
    if not settings.meta_key or not settings.baseten_key:
        raise HTTPException(status_code=500, detail="model keys missing")
    return (settings.meta_key, settings.baseten_key)


def require_meta_key(settings: Settings = Depends(get_settings)) -> str:
    """Require the Meta key, returning it for one request."""
    if not settings.meta_key:
        raise HTTPException(status_code=500, detail="model keys missing")
    return settings.meta_key


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
    """Delete every trace of one household across all stores."""
    household_id = _guard(session, household_id)
    try:
        _store().forget_household(household_id)
        AlertStore(_memory_db()).forget_household(household_id)
        photos = MeterStore(_memory_db()).forget_household(household_id)
        AuthStore(_memory_db()).forget_household(household_id)
    except (MemoryError, MeterError, AuthError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    for photo in photos:
        try:
            (_photos_dir() / Path(photo).name).unlink(missing_ok=True)
        except OSError:
            logger.warning("forgotten photo %s could not be removed", photo)
    shutil.rmtree(_art_household_dir(household_id), ignore_errors=True)
    forget_household_threads(_threads_db(), household_id)
    return {"forgotten": True}


def forget_household_threads(threads_db: Path, household_id: str) -> None:
    """Delete one household's plan threads, checkpoints, and run records.

    Only threads with a runs-table row are found; runs started before
    the runs table existed keep their checkpoints.
    """
    if not threads_db.exists():
        return
    conn = db_connect(threads_db)
    try:
        with conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            thread_ids: list[str] = []
            if "runs" in tables:
                thread_ids = [
                    str(row[0])
                    for row in conn.execute(
                        "SELECT thread_id FROM runs WHERE household_id = ?",
                        (household_id,),
                    )
                ]
                conn.execute(
                    "DELETE FROM runs WHERE household_id = ?",
                    (household_id,),
                )
            if "run_errors" in tables:
                _ensure_run_errors(conn)
                conn.execute(
                    "DELETE FROM run_errors WHERE household_id = ?",
                    (household_id,),
                )
            keys = [(thread_id,) for thread_id in thread_ids]
            if "checkpoints" in tables:
                conn.executemany("DELETE FROM checkpoints WHERE thread_id = ?", keys)
            if "writes" in tables:
                conn.executemany("DELETE FROM writes WHERE thread_id = ?", keys)
    finally:
        conn.close()


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


def get_approval_graph(
    keys: tuple[str, str] = Depends(require_model_keys),
) -> Iterator[CompiledStateGraph[PlanState, None, PlanState, PlanState]]:
    """Yield one checkpointed supervisor graph per request."""
    meta_key, baseten_key = keys
    router = ModelRouter.from_keys(meta_key, baseten_key)
    now = datetime.now(BERLIN)
    loader = partial(
        load_price_bars,
        now.date() + timedelta(days=1),
        _cache_dir(),
        datetime.now(UTC),
        DEFAULTS,
    )
    with _threads_saver(_threads_db()) as saver:
        yield build_graph(
            router,
            loader,
            checkpointer=saver,
            memory=_store(),
            wallbox=WallboxClient(),
        )


def _thread_config(thread_id: str) -> RunnableConfig:
    """Build the LangGraph config for one thread."""
    return {"configurable": {"thread_id": thread_id}}


@contextmanager
def _threads_saver(threads_db: Path) -> Iterator[SqliteSaver]:
    """Yield one checkpoint saver over a WAL plus busy-timeout connection."""
    conn = db_connect(threads_db)
    try:
        yield SqliteSaver(conn)
    finally:
        conn.close()


_RUNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    thread_id TEXT PRIMARY KEY,
    household_id TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL,
    finished_at TEXT
);
"""

RUN_TIMEOUT_MINUTES = 10

STORE_UNAVAILABLE = "plan store unavailable, retry shortly"


@dataclass
class RunRecord:
    """One background run's lifetime, tracked beside the checkpoints."""

    thread_id: str
    household_id: str
    started_at: str
    finished_at: str | None


def record_run_started(
    threads_db: Path, thread_id: str, household_id: str = ""
) -> None:
    """Persist one background run's start, resetting any earlier attempt."""
    _ensure_run_tables(threads_db)
    conn = db_connect(threads_db)
    try:
        with conn:
            conn.execute(
                "INSERT INTO runs (thread_id, household_id, started_at, finished_at)"
                " VALUES (?, ?, ?, NULL)"
                " ON CONFLICT (thread_id) DO UPDATE SET"
                " household_id = excluded.household_id,"
                " started_at = excluded.started_at, finished_at = NULL",
                (thread_id, household_id, datetime.now(UTC).isoformat()),
            )
    finally:
        conn.close()


def record_run_finished(threads_db: Path, thread_id: str) -> None:
    """Persist one background run's end, creating the row when missing."""
    stamp = datetime.now(UTC).isoformat()
    _ensure_run_tables(threads_db)
    conn = db_connect(threads_db)
    try:
        with conn:
            conn.execute(
                "INSERT INTO runs (thread_id, household_id, started_at, finished_at)"
                " VALUES (?, '', ?, ?)"
                " ON CONFLICT (thread_id) DO UPDATE SET"
                " finished_at = excluded.finished_at",
                (thread_id, stamp, stamp),
            )
    finally:
        conn.close()


def read_run(threads_db: Path, thread_id: str) -> RunRecord | None:
    """Read one run's lifetime, or None when the thread never started."""
    if not threads_db.exists():
        return None
    _ensure_run_tables(threads_db)
    conn = db_connect(threads_db)
    try:
        row = conn.execute(
            "SELECT thread_id, household_id, started_at, finished_at"
            " FROM runs WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return RunRecord(
        thread_id=str(row[0]),
        household_id=str(row[1]),
        started_at=str(row[2]),
        finished_at=str(row[3]) if row[3] is not None else None,
    )


def _run_is_stale(run: RunRecord | None) -> bool:
    """Report whether one unfinished run passed the timeout."""
    if run is None or run.finished_at is not None:
        return False
    try:
        started = datetime.fromisoformat(run.started_at)
    except ValueError:
        return False
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    return datetime.now(UTC) - started > timedelta(minutes=RUN_TIMEOUT_MINUTES)


def _read_thread_state(
    threads_db: Path, thread_id: str
) -> tuple[CheckpointTuple | None, RunRecord | None, str | None, str | None]:
    """Fetch one thread's checkpoint, run row, and crash records."""
    with _threads_saver(threads_db) as saver:
        snapshot = saver.get_tuple(_thread_config(thread_id))
    run = read_run(threads_db, thread_id)
    recorded = read_run_error(threads_db, thread_id)
    recorded_owner = read_run_owner(threads_db, thread_id) if run is None else None
    return snapshot, run, recorded, recorded_owner


def _snapshot_values(snapshot: CheckpointTuple | None) -> dict[str, Any]:
    """Return one checkpoint's channel values, tolerating missing data."""
    if snapshot is None:
        return {}
    values = snapshot.checkpoint.get("channel_values")
    return values if isinstance(values, dict) else {}


def _snapshot_interrupts(snapshot: CheckpointTuple | None) -> list[dict[str, Any]]:
    """Return one checkpoint's pending interrupt payloads, oldest first."""
    found: list[dict[str, Any]] = []
    if snapshot is None or snapshot.pending_writes is None:
        return found
    for _task_id, channel, value in snapshot.pending_writes:
        if channel != "__interrupt__":
            continue
        items = value if isinstance(value, list) else [value]
        for item in items:
            review = getattr(item, "value", item)
            found.append(review if isinstance(review, dict) else {})
    return found


def _stale_error() -> str:
    """Explain one timed-out run with a retry hint."""
    return (
        f"run timed out after {RUN_TIMEOUT_MINUTES} minutes without progress;"
        " start a new plan to retry"
    )


def _status_from_snapshot(
    thread_id: str,
    snapshot: CheckpointTuple | None,
    run: RunRecord | None,
    recorded: str | None,
    recorded_owner: str | None = None,
    owner: str | None = None,
) -> ApprovalStatus:
    """Derive one thread's status from a checkpoint plus the run records."""
    values = _snapshot_values(snapshot)
    if not values:
        if recorded is None and run is None:
            raise HTTPException(status_code=404, detail="unknown thread")
        household = run.household_id if run else (recorded_owner or "")
        if owner is not None and household and household != owner:
            raise HTTPException(status_code=403, detail="thread belongs elsewhere")
        if recorded is not None:
            return ApprovalStatus(thread_id=thread_id, status="blocked", error=recorded)
        if run is not None and run.finished_at is not None:
            return ApprovalStatus(thread_id=thread_id, status="done")
        if _run_is_stale(run):
            return ApprovalStatus(
                thread_id=thread_id, status="blocked", error=_stale_error()
            )
        return ApprovalStatus(thread_id=thread_id, status="running")
    if owner is not None:
        claimed: str = values.get("household_id") or ""
        if not claimed:
            claimed = (run.household_id if run else "") or (recorded_owner or "")
        if claimed and claimed != owner:
            raise HTTPException(status_code=403, detail="thread belongs elsewhere")
    interrupts = _snapshot_interrupts(snapshot)
    if interrupts:
        review = interrupts[0]
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
    if recorded is not None:
        return ApprovalStatus(thread_id=thread_id, status="blocked", error=recorded)
    if values.get("published") is True:
        return ApprovalStatus(thread_id=thread_id, status="published", published=True)
    if values.get("error"):
        return ApprovalStatus(
            thread_id=thread_id, status="blocked", error=str(values["error"])
        )
    if run is not None and run.finished_at is not None:
        return ApprovalStatus(thread_id=thread_id, status="done")
    if _run_is_stale(run):
        return ApprovalStatus(
            thread_id=thread_id, status="blocked", error=_stale_error()
        )
    if run is None:
        return ApprovalStatus(thread_id=thread_id, status="done")
    return ApprovalStatus(thread_id=thread_id, status="running")


@dataclass
class PlanReader:
    """Keyless read access to the thread database."""

    threads_db: Path


def get_plan_reader() -> PlanReader:
    """Build the keyless thread reader for one request."""
    return PlanReader(threads_db=_threads_db())


@app.get("/approvals/threads/{thread_id}", response_model=ApprovalStatus)
def read_thread(
    thread_id: str,
    reader: PlanReader = Depends(get_plan_reader),
    session: Session = Depends(current_session),
) -> ApprovalStatus:
    """Report one thread's approval state without model keys."""
    try:
        snapshot, run, recorded, recorded_owner = _read_thread_state(
            reader.threads_db, thread_id
        )
    except sqlite3.Error as exc:
        logger.exception("thread read %s failed", thread_id)
        raise HTTPException(status_code=503, detail=STORE_UNAVAILABLE) from exc
    return _status_from_snapshot(
        thread_id, snapshot, run, recorded, recorded_owner, session.household_id
    )


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
    try:
        state = _read_thread_state(_threads_db(), thread_id)
    except sqlite3.Error as exc:
        logger.exception("thread read %s failed", thread_id)
        raise HTTPException(status_code=503, detail=STORE_UNAVAILABLE) from exc
    current = _status_from_snapshot(thread_id, *state, session.household_id)
    if current.status != "paused":
        raise HTTPException(status_code=409, detail="thread is not awaiting approval")
    try:
        graph.invoke(
            Command(resume={"approved": body.approved}),
            _thread_config(thread_id),
        )
    finally:
        record_run_finished(_threads_db(), thread_id)
    try:
        state = _read_thread_state(_threads_db(), thread_id)
    except sqlite3.Error as exc:
        logger.exception("thread read %s failed", thread_id)
        raise HTTPException(status_code=503, detail=STORE_UNAVAILABLE) from exc
    return _status_from_snapshot(thread_id, *state, session.household_id)


class AlertsResponse(BaseModel):
    """One household's alerts, oldest first."""

    household_id: str
    alerts: list[Alert]


def get_watch_router(
    keys: tuple[str, str] = Depends(require_model_keys),
) -> ModelRouter:
    """Build the production router for one watcher pass."""
    return ModelRouter.from_keys(*keys)


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


def get_meter_vision(
    keys: tuple[str, str] = Depends(require_model_keys),
) -> MeterVision:
    """Build the production vision deps for one request."""
    meta_key, baseten_key = keys
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


_PHOTO_MIME_EXTENSIONS = {
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
    photo, mime = _read_photo(file)
    extension = _PHOTO_MIME_EXTENSIONS[mime]
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
            for kind, extension in _PHOTO_MIME_EXTENSIONS.items()
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
    note: str = Field(default="", max_length=2000)


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
        text = f"{feedback.device}: {feedback.verdict}"
        if feedback.note.strip():
            text += f" ({feedback.note.strip()})"
        latest = store.list_episodes(household_id, kind="feedback", limit=1)
        if latest and latest[0].text == text:
            return FeedbackResponse(
                household_id=household_id,
                episode=latest[0],
                learned_windows=current,
            )
        learned = update_from_feedback(feedback, current)
        store.set_preference(household_id, LEARNED_KEY, learned)
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


class AskCitation(BaseModel):
    """One tariff-guide source behind an answer."""

    title: str
    source_name: str
    source_url: str


class AskResponse(BaseModel):
    """One answered why-question with its cited sources."""

    question: str
    answer: str
    citations: list[AskCitation]
    model: str


def get_ask_router(
    keys: tuple[str, str] = Depends(require_model_keys),
) -> ModelRouter:
    """Build the production router for one Ask-Why answer."""
    return ModelRouter.from_keys(*keys)


_ASK_SYSTEM = {
    "de": (
        "Beantworte die Frage in höchstens drei Sätzen auf Deutsch,"
        " nur aus den Passagen. Zitiere mit [1], [2] und erfinde nichts."
    ),
    "en": (
        "Answer the question in at most three sentences in English,"
        " using only the passages. Cite with [1], [2]; invent nothing."
    ),
}

_ASK_EMPTY = {
    "de": (
        "Dazu steht nichts in der Tarifhilfe. Frage zum Beispiel nach"
        " Umlagen, Netzentgelten oder Spotpreisen."
    ),
    "en": (
        "The tariff guide says nothing about that. Try asking about"
        " levies, grid fees, or spot prices."
    ),
}


@app.get("/ask", response_model=AskResponse)
def ask_why(
    household_id: str,
    q: str = Query(max_length=500),
    lang: Literal["de", "en"] = "de",
    router: ModelRouter = Depends(get_ask_router),
    keys: tuple[str, str] = Depends(require_model_keys),
    session: Session = Depends(current_session),
) -> AskResponse:
    """Answer one why-question from the tariff guide with citations."""
    household_id = _guard(session, household_id)
    question = q.strip()
    if not question:
        raise HTTPException(status_code=422, detail="q must not be blank")
    retriever = Retriever(load_corpus())
    hits = retriever.retrieve(question, k=5)
    if not hits:
        return AskResponse(
            question=question, answer=_ASK_EMPTY[lang], citations=[], model="none"
        )
    meta_key, baseten_key = keys
    reranked = retriever.rerank(
        question,
        hits,
        BasetenClient(
            baseten_key, fallback=ChatClient(META_BASE_URL, meta_key, SPARK_MODEL)
        ),
    )
    top = reranked[:3]
    passages = "\n\n".join(
        f"[{number}] {hit.title}: {hit.text} ({hit.source_name})"
        for number, hit in enumerate(top, start=1)
    )
    try:
        result = router.chat(
            "ask",
            [
                Message(role="system", content=_ASK_SYSTEM[lang]),
                Message(role="user", content=f"Question: {question}\n{passages}"),
            ],
            300,
        )
    except LlmError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return AskResponse(
        question=question,
        answer=result.content.strip(),
        citations=[
            AskCitation(
                title=hit.title,
                source_name=hit.source_name,
                source_url=hit.source_url,
            )
            for hit in top
        ],
        model=result.model,
    )


class MonthlyReportResponse(BaseModel):
    """One monthly report plus its cached illustration, if any."""

    report: MonthlyReport
    illustration_data_url: str | None


class IllustrationResponse(BaseModel):
    """One report illustration with its cache state."""

    month: str
    illustration_data_url: str
    cached: bool


def get_image_client(meta_key: str = Depends(require_meta_key)) -> ImageClient:
    """Build the production image client for one request."""
    return ImageClient(meta_key)


def _art_dir() -> Path:
    """Return the report art directory, honoring REPORT_ART_DIR."""
    override = os.environ.get("REPORT_ART_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent.parent / "data" / "report_art"


def _art_household_dir(household_id: str) -> Path:
    """Return the cached art directory, keyed by household hash."""
    digest = hashlib.sha1(household_id.encode("utf-8")).hexdigest()[:16]
    return _art_dir() / digest


def _art_path(household_id: str, month: str) -> Path:
    """Return the cached art file, keyed by household hash."""
    return _art_household_dir(household_id) / f"{month}.png"


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


ROOF_PROMPT = "roof surface"

_PREVIEW_PROMPTS = {
    "solar": (
        "Photorealistic edit: add modern black solar panels covering"
        " the main roof surface. Keep the house, garden, sky, and photo"
        " style unchanged."
    ),
    "heat_pump": (
        "Photorealistic edit: add a modern outdoor heat pump unit beside"
        " the house wall. Keep the house, garden, sky, and photo style"
        " unchanged."
    ),
    "facade": (
        "Photorealistic edit: show the house with fresh modern insulated"
        " facade cladding in a warm neutral tone. Keep the roof shape,"
        " windows, garden, sky, and photo style unchanged."
    ),
}


def get_sam_client(meta_key: str = Depends(require_meta_key)) -> SamClient:
    """Build the production SAM client for one request."""
    return SamClient(meta_key)


class RoofBoxOut(BaseModel):
    """One detected roof box in source pixels."""

    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float | None


class RoofEstimateOut(BaseModel):
    """One roof's panel fit with its assumptions."""

    roof_share: float
    roof_m2: float | None
    usable_m2: float | None
    panels: int | None
    kwp: float | None
    kwh_per_year: float | None
    assumptions: list[str]


class MeasureResponse(BaseModel):
    """Roof boxes plus the panel estimate, if a roof was found."""

    household_id: str
    width: int
    height: int
    boxes: list[RoofBoxOut]
    estimate: RoofEstimateOut | None
    note: str


class PreviewResponse(BaseModel):
    """One renovation preview with its AI label."""

    household_id: str
    style: str
    image_data_url: str
    ai_label: str


_READ_CHUNK_BYTES = 1024 * 1024


def _read_capped(body: BinaryIO, limit: int) -> bytes:
    """Stream one upload body, stopping as soon as it passes the limit."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = body.read(_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(status_code=422, detail="photo exceeds 10 MB")
        chunks.append(chunk)
    return b"".join(chunks)


def _read_photo(file: UploadFile) -> tuple[bytes, str]:
    """Read and validate one uploaded photo."""
    mime = file.content_type or ""
    if mime not in _PHOTO_MIME_EXTENSIONS:
        raise HTTPException(status_code=422, detail="photo must be an image")
    if file.size is not None and file.size > _MAX_PHOTO_BYTES:
        raise HTTPException(status_code=422, detail="photo exceeds 10 MB")
    return _read_capped(file.file, _MAX_PHOTO_BYTES), mime


@app.post("/solar/measure", response_model=MeasureResponse)
def measure_roof(
    household_id: str,
    file: UploadFile = File(...),
    roof_width_m: float | None = Query(default=None, gt=0),
    lang: Literal["de", "en"] = "de",
    sam: SamClient = Depends(get_sam_client),
    session: Session = Depends(current_session),
) -> MeasureResponse:
    """Outline the roof in one house photo and estimate the panel fit."""
    household_id = _guard(session, household_id)
    photo, mime = _read_photo(file)
    try:
        with Image.open(io.BytesIO(photo)) as image:
            width, height = image.size
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=422, detail="photo unreadable") from exc
    try:
        boxes = sam.segment(base64.b64encode(photo).decode("ascii"), mime, ROOF_PROMPT)
    except LlmError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    english = lang == "en"
    estimate = estimate_roof(boxes, roof_width_m)
    if estimate is None:
        note = (
            "No roof found in this photo. Try a straight-on daylight shot."
            if english
            else "Kein Dach auf diesem Foto gefunden. Versuche eine frontale"
            " Tageslichtaufnahme."
        )
        return MeasureResponse(
            household_id=household_id,
            width=width,
            height=height,
            boxes=[],
            estimate=None,
            note=note,
        )
    return MeasureResponse(
        household_id=household_id,
        width=width,
        height=height,
        boxes=[
            RoofBoxOut(
                x1=box.x1,
                y1=box.y1,
                x2=box.x2,
                y2=box.y2,
                confidence=box.confidence,
            )
            for box in boxes
        ],
        estimate=RoofEstimateOut(
            roof_share=estimate.roof_share,
            roof_m2=estimate.roof_m2,
            usable_m2=estimate.usable_m2,
            panels=estimate.panels,
            kwp=estimate.kwp,
            kwh_per_year=estimate.kwh_per_year,
            assumptions=list(estimate.assumptions),
        ),
        note="",
    )


@app.post("/solar/preview", response_model=PreviewResponse)
def preview_renovation(
    household_id: str,
    style: Literal["solar", "heat_pump", "facade"],
    file: UploadFile = File(...),
    lang: Literal["de", "en"] = "de",
    images: ImageClient = Depends(get_image_client),
    session: Session = Depends(current_session),
) -> PreviewResponse:
    """Render one renovation style onto the household's own photo."""
    household_id = _guard(session, household_id)
    photo, _ = _read_photo(file)
    try:
        edited = images.edit(photo, _PREVIEW_PROMPTS[style])
    except LlmError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    label = (
        "AI visualization — not a photo of a real installation."
        if lang == "en"
        else "KI-Visualisierung – kein Foto einer echten Anlage."
    )
    return PreviewResponse(
        household_id=household_id,
        style=style,
        image_data_url="data:image/png;base64,"
        + base64.b64encode(edited).decode("ascii"),
        ai_label=label,
    )


@dataclass(frozen=True)
class PlanRunner:
    """One request's planning deps: router, loader, stores, wallbox."""

    router: ChatRouter
    loader_for: Callable[[date], PriceLoader]
    threads_db: Path
    memory: MemoryStore
    wallbox: WallboxDriver


_RUN_ERRORS_SCHEMA = """
CREATE TABLE IF NOT EXISTS run_errors (
    thread_id TEXT PRIMARY KEY,
    message TEXT NOT NULL,
    household_id TEXT NOT NULL DEFAULT ''
);
"""


def _ensure_run_errors(conn: sqlite3.Connection) -> None:
    """Create the crash table, migrating older databases in place."""
    conn.executescript(_RUN_ERRORS_SCHEMA)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(run_errors)")}
    if "household_id" not in columns:
        conn.execute(
            "ALTER TABLE run_errors ADD COLUMN household_id TEXT NOT NULL DEFAULT ''"
        )


_RUN_TABLES_READY: set[Path] = set()


def _ensure_run_tables(threads_db: Path) -> None:
    """Create the runs and crash tables once per database file."""
    if threads_db in _RUN_TABLES_READY:
        return
    conn = db_connect(threads_db)
    try:
        with conn:
            conn.executescript(_RUNS_SCHEMA)
            _ensure_run_errors(conn)
    finally:
        conn.close()
    _RUN_TABLES_READY.add(threads_db)


def record_run_error(
    threads_db: Path, thread_id: str, message: str, household_id: str = ""
) -> None:
    """Persist one background-run crash beside the checkpoints."""
    _ensure_run_tables(threads_db)
    conn = db_connect(threads_db)
    try:
        with conn:
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
    _ensure_run_tables(threads_db)
    conn = db_connect(threads_db)
    try:
        row = conn.execute(
            "SELECT message FROM run_errors WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
    finally:
        conn.close()
    return str(row[0]) if row else None


def read_run_owner(threads_db: Path, thread_id: str) -> str | None:
    """Read one recorded crash's household, or None when unknown."""
    if not threads_db.exists():
        return None
    _ensure_run_tables(threads_db)
    conn = db_connect(threads_db)
    try:
        row = conn.execute(
            "SELECT household_id FROM run_errors WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
    finally:
        conn.close()
    return str(row[0]) if row and row[0] else None


def get_plan_runner(
    keys: tuple[str, str] = Depends(require_model_keys),
) -> PlanRunner:
    """Build the production planning deps for one request."""
    meta_key, baseten_key = keys
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
    text: str = Field(max_length=2000)
    plan_day: date | None = None
    lang: Literal["de", "en"] = "de"


class PlanCreated(BaseModel):
    """One accepted planning run."""

    thread_id: str
    status: str


class PlanPriceBar(BaseModel):
    """One priced hour backing the plan timeline shading."""

    hour: int
    price_ct_kwh: float
    source: str
    start_utc: str | None = None


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
    plan_day: str | None = None
    price_source: str | None = None
    price_stale: bool = False
    attribution: dict[str, str] = {}
    prices: list[PlanPriceBar] | None = None


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
        try:
            with _threads_saver(runner.threads_db) as saver:
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
    finally:
        record_run_finished(runner.threads_db, thread_id)


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
    record_run_started(runner.threads_db, thread_id, household_id)
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
    reader: PlanReader = Depends(get_plan_reader),
    session: Session = Depends(current_session),
) -> PlanDetail:
    """Read one thread's plan state without model keys."""
    try:
        snapshot, run, recorded, recorded_owner = _read_thread_state(
            reader.threads_db, thread_id
        )
    except sqlite3.Error as exc:
        logger.exception("plan read %s failed", thread_id)
        raise HTTPException(status_code=503, detail=STORE_UNAVAILABLE) from exc
    current = _status_from_snapshot(
        thread_id, snapshot, run, recorded, recorded_owner, session.household_id
    )
    status = current.status
    values = _snapshot_values(snapshot)
    audit = values.get("audit", [])
    plan_day = values.get("plan_day")
    price_source = values.get("price_source")
    raw_attribution = values.get("attribution", {})
    raw_prices = values.get("prices")
    prices: list[PlanPriceBar] | None = None
    if isinstance(raw_prices, list):
        bars: list[PlanPriceBar] = []
        for bar in raw_prices:
            if (
                isinstance(bar, dict)
                and isinstance(bar.get("hour"), int)
                and isinstance(bar.get("price_ct_kwh"), (int, float))
            ):
                start_utc = bar.get("start_utc")
                bars.append(
                    PlanPriceBar(
                        hour=bar["hour"],
                        price_ct_kwh=float(bar["price_ct_kwh"]),
                        source=str(bar.get("source", "unknown")),
                        start_utc=str(start_utc) if start_utc is not None else None,
                    )
                )
        prices = bars
    error = recorded if recorded is not None else values.get("error")
    if error is None:
        error = current.error
    return PlanDetail(
        thread_id=thread_id,
        status=status,
        schedule=values.get("schedule"),
        narration=values.get("narration"),
        citations=values.get("citations"),
        total_cost_eur=values.get("total_cost_eur"),
        error=str(error) if error is not None else None,
        audit=[str(event) for event in audit] if isinstance(audit, list) else [],
        plan_day=plan_day if isinstance(plan_day, str) else None,
        price_source=price_source if isinstance(price_source, str) else None,
        price_stale=values.get("price_stale") is True,
        attribution=(
            {str(block): str(model) for block, model in raw_attribution.items()}
            if isinstance(raw_attribution, dict)
            else {}
        ),
        prices=prices,
    )


def _trace_events(
    thread_id: str, threads_db: Path, max_polls: int = 750, interval: float = 0.4
) -> Iterator[str]:
    """Yield new audit lines until the thread settles or time runs out."""
    seen = 0
    try:
        for _ in range(max_polls):
            try:
                snapshot, run, recorded, recorded_owner = _read_thread_state(
                    threads_db, thread_id
                )
            except sqlite3.Error:
                logger.exception("trace poll %s failed", thread_id)
                return
            try:
                current = _status_from_snapshot(
                    thread_id, snapshot, run, recorded, recorded_owner
                )
            except HTTPException:
                return
            values = _snapshot_values(snapshot)
            audit = values.get("audit", [])
            lines = [str(event) for event in audit] if isinstance(audit, list) else []
            for line in lines[seen:]:
                yield f"data: {line}\n\n"
            seen = len(lines)
            if current.status in ("published", "done", "blocked"):
                return
            time.sleep(interval)
    finally:
        yield "data: [done]\n\n"


@app.get("/plan/{thread_id}/trace")
def stream_trace(
    thread_id: str,
    reader: PlanReader = Depends(get_plan_reader),
    session: Session = Depends(current_session),
) -> StreamingResponse:
    """Stream one thread's audit trace as server-sent events."""
    try:
        snapshot, run, recorded, recorded_owner = _read_thread_state(
            reader.threads_db, thread_id
        )
    except sqlite3.Error as exc:
        logger.exception("trace read %s failed", thread_id)
        raise HTTPException(status_code=503, detail=STORE_UNAVAILABLE) from exc
    _status_from_snapshot(
        thread_id, snapshot, run, recorded, recorded_owner, session.household_id
    )
    return StreamingResponse(
        _trace_events(thread_id, reader.threads_db), media_type="text/event-stream"
    )


def get_wallbox_client() -> WallboxDriver:
    """Build the wallbox driver for one request (local simulator)."""
    return WallboxClient()


@app.get("/wallbox/status", response_model=WallboxStatus)
def read_wallbox_status(
    wallbox: WallboxDriver = Depends(get_wallbox_client),
    session: Session = Depends(current_session),
) -> WallboxStatus:
    """Report the wallbox live status."""
    del session
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
    session: Session = Depends(current_session),
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
    logger.info(
        "wallbox programmed by %s: %s to %s at %.1f kW",
        session.household_id,
        start_iso,
        end_iso,
        body.max_kw,
    )
    try:
        return wallbox.program(start_iso, end_iso, body.max_kw)
    except WallboxError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
