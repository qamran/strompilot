"""Wallbox physics: plug, program, charge, and a movable clock."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

HARDWARE_MAX_KW = 22.0
_MAX_ADVANCE_MINUTES = 24 * 60


class SimError(Exception):
    """Invalid wallbox input or an impossible physical action."""


class Sim:
    """One simulated wallbox with JSON-persisted state.

    State survives process restarts so the MCP server can run
    spawn-per-call: every call loads, acts, and saves.
    """

    def __init__(self, path: Path, state: dict[str, Any]) -> None:
        self._path = path
        self._state = state

    @classmethod
    def load(cls, path: Path, now: datetime) -> "Sim":
        """Load stored state, or start fresh at the given instant."""
        if path.exists():
            state = json.loads(path.read_text(encoding="utf-8"))
            return cls(path, state)
        return cls(
            path,
            {
                "plugged": False,
                "manual": False,
                "max_kw": 0.0,
                "session_kwh": 0.0,
                "total_kwh": 0.0,
                "sim_now": now.isoformat(),
                "program": None,
            },
        )

    def _save(self) -> None:
        """Persist the current state to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._state), encoding="utf-8")

    def _now(self) -> datetime:
        """Return the simulator clock."""
        return datetime.fromisoformat(str(self._state["sim_now"]))

    def status(self) -> dict[str, Any]:
        """Report the full live state with derived charging fields."""
        charging, power = self._drive(self._now())
        return {
            "plugged": self._state["plugged"],
            "charging": charging,
            "power_kw": power,
            "max_kw": self._state["max_kw"],
            "session_kwh": round(float(self._state["session_kwh"]), 3),
            "total_kwh": round(float(self._state["total_kwh"]), 3),
            "sim_now": self._state["sim_now"],
            "program": self._state["program"],
        }

    def plug(self) -> dict[str, Any]:
        """Plug the car in."""
        self._state["plugged"] = True
        self._save()
        return self.status()

    def unplug(self) -> dict[str, Any]:
        """Unplug the car, ending any session."""
        self._state["plugged"] = False
        self._state["manual"] = False
        self._state["session_kwh"] = 0.0
        self._save()
        return self.status()

    def start_now(self, max_kw: float) -> dict[str, Any]:
        """Charge immediately at up to max_kw."""
        if not self._state["plugged"]:
            raise SimError("car is not plugged in")
        self._state["manual"] = True
        self._state["max_kw"] = self._checked_power(max_kw)
        self._save()
        return self.status()

    def stop_now(self) -> dict[str, Any]:
        """Stop charging and clear manual mode plus any program."""
        self._state["manual"] = False
        self._state["program"] = None
        self._state["session_kwh"] = 0.0
        self._save()
        return self.status()

    def program_charge(
        self, start_iso: str, end_iso: str, max_kw: float
    ) -> dict[str, Any]:
        """Program one charge window; the clock drives the rest."""
        try:
            start = datetime.fromisoformat(start_iso)
            end = datetime.fromisoformat(end_iso)
        except ValueError as exc:
            raise SimError(f"bad time: {exc}") from exc
        if end <= start:
            raise SimError("program end must be after start")
        self._state["program"] = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "max_kw": self._checked_power(max_kw),
        }
        self._save()
        return self.status()

    def advance_clock(self, minutes: int) -> dict[str, Any]:
        """Move the clock, integrating energy across program edges."""
        if minutes <= 0:
            raise SimError("advance must be positive minutes")
        if minutes > _MAX_ADVANCE_MINUTES:
            raise SimError("advance capped at 24 hours per call")
        old = self._now()
        new = old + timedelta(minutes=minutes)
        energy = self._energy_between(old, new)
        self._state["session_kwh"] = float(self._state["session_kwh"]) + energy
        self._state["total_kwh"] = float(self._state["total_kwh"]) + energy
        self._state["sim_now"] = new.isoformat()
        self._save()
        return self.status()

    @staticmethod
    def _checked_power(max_kw: float) -> float:
        """Validate one power limit against the hardware cap."""
        if max_kw <= 0:
            raise SimError("power must be positive")
        if max_kw > HARDWARE_MAX_KW:
            raise SimError(f"power capped at {HARDWARE_MAX_KW:.0f} kW")
        return max_kw

    def _drive(self, moment: datetime) -> tuple[bool, float]:
        """Decide charging and power at one instant."""
        if not self._state["plugged"]:
            return False, 0.0
        if self._state["manual"]:
            return True, float(self._state["max_kw"])
        program = self._state["program"]
        if program is None:
            return False, 0.0
        start = datetime.fromisoformat(program["start"])
        end = datetime.fromisoformat(program["end"])
        if start <= moment < end:
            return True, float(program["max_kw"])
        return False, 0.0

    def _energy_between(self, old: datetime, new: datetime) -> float:
        """Integrate kWh over one advance, splitting at program edges."""
        if not self._state["plugged"]:
            return 0.0
        if self._state["manual"]:
            hours = (new - old).total_seconds() / 3600
            return float(self._state["max_kw"]) * hours
        program = self._state["program"]
        if program is None:
            return 0.0
        start = datetime.fromisoformat(program["start"])
        end = datetime.fromisoformat(program["end"])
        overlap = min(new, end) - max(old, start)
        if overlap.total_seconds() <= 0:
            return 0.0
        return float(program["max_kw"]) * overlap.total_seconds() / 3600
