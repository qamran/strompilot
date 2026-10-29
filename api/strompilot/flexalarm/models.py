"""Flex-Alarm data models."""

from datetime import date, datetime

from pydantic import BaseModel


class AlertCandidate(BaseModel):
    """One price window the triage judge may turn into an alert."""

    kind: str
    day: date
    start: str
    end: str
    avg_ct_kwh: float
    mean_ct_kwh: float
    extreme_ct_kwh: float
    hours: float


class TriageVerdict(BaseModel):
    """The judge's call: fire the alert or stay silent, with a reason."""

    fire: bool
    reason: str


class Alert(BaseModel):
    """One stored alert with its delivery state."""

    id: int
    household_id: str
    dedup_key: str
    kind: str
    title: str
    body: str
    status: str
    channel: str | None
    reason: str
    created_at: datetime


class WatchReport(BaseModel):
    """One watcher pass over one household."""

    household_id: str
    day: date
    candidates: int
    fired: int
    held: int
    delivered: int
    released: int = 0
    skipped: int
    duplicates: int
    errors: list[str]
