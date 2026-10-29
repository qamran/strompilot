"""Window shifts: apply learned prefs to extracted constraints."""

from collections.abc import Mapping
from typing import Any

from strompilot.lifeplan.schemas import HouseholdConstraints

_FOLD = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
_DAY_MINUTES = 24 * 60


def _to_minutes(clock: str) -> int:
    """Convert HH:MM to minutes since midnight."""
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


def _to_clock(minutes: int) -> str:
    """Convert minutes since midnight back to HH:MM."""
    clamped = max(0, min(_DAY_MINUTES - 60, minutes))
    return f"{clamped // 60:02d}:{clamped % 60:02d}"


def _shifted(start: int, end: int, earliest: int, latest: int) -> tuple[int, int]:
    """Shift one window, wrapping overnight starts past midnight."""
    moved_start = start + earliest * 60
    moved_end = max(0, min(_DAY_MINUTES - 60, end + latest * 60))
    if start > end:
        moved_start %= _DAY_MINUTES
    else:
        moved_start = max(0, min(_DAY_MINUTES - 60, moved_start))
        moved_start = min(moved_start, moved_end)
    return moved_start, moved_end


def _fold(name: str) -> str:
    """Fold a device name for tolerant matching."""
    return name.strip().lower().translate(_FOLD)


def apply_learned_windows(
    constraints: HouseholdConstraints, learned: Mapping[str, Any]
) -> HouseholdConstraints:
    """Shift each matched window by its learned hours, clamped to the day.

    Malformed entries are ignored so one bad pref can never break a
    plan; fixed devices keep their exact times.
    """
    folded = {
        _fold(name): entry for name, entry in learned.items() if isinstance(name, str)
    }
    devices = []
    for device in constraints.devices:
        entry = folded.get(_fold(device.device))
        if not device.shiftable or not isinstance(entry, Mapping):
            devices.append(device)
            continue
        earliest = entry.get("earliest_shift_h", 0)
        latest = entry.get("latest_shift_h", 0)
        if not isinstance(earliest, int) or not isinstance(latest, int):
            devices.append(device)
            continue
        start, end = _shifted(
            _to_minutes(device.earliest),
            _to_minutes(device.latest),
            earliest,
            latest,
        )
        devices.append(
            device.model_copy(
                update={"earliest": _to_clock(start), "latest": _to_clock(end)}
            )
        )
    return HouseholdConstraints(devices=devices, notes=constraints.notes)
