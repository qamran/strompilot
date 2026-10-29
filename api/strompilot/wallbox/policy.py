"""Charge policy: what the agent may ask the wallbox to do."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ChargePolicy:
    """Agent-side limits: power cap plus hardware class."""

    max_kw: float = 11.0
    hardware: str = "simulated"


@dataclass(frozen=True)
class PolicyDecision:
    """One gate verdict with its human-readable reason."""

    allowed: bool
    reason: str


def authorize(
    policy: ChargePolicy, start_iso: str, end_iso: str, max_kw: float
) -> PolicyDecision:
    """Judge one programmed charge against the policy gates."""
    if policy.hardware != "simulated":
        return PolicyDecision(False, "real hardware needs human approval")
    try:
        start = datetime.fromisoformat(start_iso)
        end = datetime.fromisoformat(end_iso)
    except ValueError:
        return PolicyDecision(False, "bad window times")
    if end <= start:
        return PolicyDecision(False, "window end must be after start")
    if max_kw <= 0:
        return PolicyDecision(False, "power must be positive")
    if max_kw > policy.max_kw:
        return PolicyDecision(
            False, f"power {max_kw} kW exceeds policy {policy.max_kw} kW"
        )
    return PolicyDecision(True, "ok")
