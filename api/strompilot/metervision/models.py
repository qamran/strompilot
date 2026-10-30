"""Meter vision data models."""

from datetime import datetime

from pydantic import BaseModel


class MeterError(Exception):
    """Invalid meter input: bad photos, unreadable digits, bad values."""


class DigitReading(BaseModel):
    """One vision reading with the model's own confidence."""

    value_kwh: float
    confidence: str


class SerialReading(BaseModel):
    """One meter serial number, or null when the photo hides it."""

    serial: str | None


class MeterReading(BaseModel):
    """One proposed or confirmed meter reading."""

    id: int
    household_id: str
    value_kwh: float
    read_at: datetime
    status: str
    confidence: str
    sam_box: str | None
    photo_path: str
    serial: str | None = None
    created_at: datetime


class Calibration(BaseModel):
    """Annual use extrapolated from two confirmed readings."""

    annual_kwh: float
    kwh_per_day: float
    days: float
    from_reading_id: int
    to_reading_id: int


class PlanTotals(BaseModel):
    """One day's plan economics: devices plus calibrated background."""

    day: str
    annual_kwh: float
    device_cost_eur: float
    baseline_kwh: float
    baseline_cost_eur: float
    total_eur: float
    slots: int


class ReplanDiff(BaseModel):
    """Old versus new plan totals after a calibration change."""

    before: PlanTotals
    after: PlanTotals
    devices_unchanged: bool
    note: str
