"""Quiet hours: no deliveries while the household sleeps."""

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator

from strompilot.prices.models import BERLIN

_CLOCK = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

DEFAULT_START = "22:00"
DEFAULT_END = "07:00"


class QuietHours(BaseModel):
    """Daily do-not-disturb window as HH:MM wall-clock bounds."""

    start: str = DEFAULT_START
    end: str = DEFAULT_END

    @field_validator("start", "end")
    @classmethod
    def _clock(cls, value: str) -> str:
        if not _CLOCK.match(value):
            raise ValueError(f"not a clock time: {value!r}")
        return value

    def minutes(self) -> tuple[int, int]:
        """Return the start and end bounds as minutes since midnight."""
        start_match = _CLOCK.match(self.start)
        end_match = _CLOCK.match(self.end)
        assert start_match is not None and end_match is not None
        start = int(start_match.group(1)) * 60 + int(start_match.group(2))
        end = int(end_match.group(1)) * 60 + int(end_match.group(2))
        return start, end


def parse_quiet_hours(value: Any) -> QuietHours:
    """Read quiet hours from a preference, defaulting on bad input."""
    if isinstance(value, dict):
        start = value.get("start")
        end = value.get("end")
        if isinstance(start, str) and isinstance(end, str):
            try:
                return QuietHours(start=start, end=end)
            except ValueError:
                pass
    return QuietHours()


def is_quiet(now: datetime, quiet: QuietHours) -> bool:
    """Tell whether one instant falls inside quiet hours."""
    berlin = now.astimezone(BERLIN)
    minute = berlin.hour * 60 + berlin.minute
    start, end = quiet.minutes()
    if start <= end:
        return start <= minute < end
    return minute >= start or minute < end
