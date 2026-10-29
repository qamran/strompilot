"""Preference updater: verdicts become per-device window shifts."""

from collections.abc import Mapping
from typing import Any

from .models import Feedback, LearningError

LEARNED_KEY = "learned_windows"
_MAX_SHIFT_H = 12


def _clamp(shift: int) -> int:
    """Bound one accumulated shift to a sane range."""
    return max(-_MAX_SHIFT_H, min(_MAX_SHIFT_H, shift))


def update_from_feedback(
    feedback: Feedback, current: Mapping[str, Any]
) -> dict[str, dict[str, int]]:
    """Fold one verdict into the learned window shifts.

    too_early pushes the window start later, too_late pulls the window
    end earlier, and good records nothing. Shifts accumulate per device
    so repeated feedback keeps moving the window.
    """
    device = feedback.device.strip()
    if not device:
        raise LearningError("device must name the device")
    merged: dict[str, dict[str, int]] = {}
    for name, entry in current.items():
        if isinstance(entry, Mapping):
            earliest = entry.get("earliest_shift_h", 0)
            latest = entry.get("latest_shift_h", 0)
            if isinstance(earliest, int) and isinstance(latest, int):
                merged[name] = {
                    "earliest_shift_h": earliest,
                    "latest_shift_h": latest,
                }
    if feedback.verdict == "good":
        return merged
    entry = merged.get(device, {"earliest_shift_h": 0, "latest_shift_h": 0})
    if feedback.verdict == "too_early":
        entry = {
            "earliest_shift_h": _clamp(entry["earliest_shift_h"] + 1),
            "latest_shift_h": entry["latest_shift_h"],
        }
    else:
        entry = {
            "earliest_shift_h": entry["earliest_shift_h"],
            "latest_shift_h": _clamp(entry["latest_shift_h"] - 1),
        }
    merged[device] = entry
    return merged
