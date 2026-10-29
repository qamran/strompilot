"""Memory data models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class MemoryError(Exception):
    """Invalid memory input: blank ids, keys, kinds, or texts."""


class Preference(BaseModel):
    """One household preference with its update time."""

    household_id: str
    key: str
    value: Any
    updated_at: datetime


class Episode(BaseModel):
    """One timestamped household memory."""

    id: int
    household_id: str
    kind: str
    text: str
    created_at: datetime
