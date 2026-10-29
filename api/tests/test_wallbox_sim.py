"""Tests for the wallbox simulator physics."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from wallbox.sim import HARDWARE_MAX_KW, Sim, SimError

BERLIN = ZoneInfo("Europe/Berlin")


def at(day: int, hour: int, minute: int = 0) -> datetime:
    """Build a Berlin wall-clock instant in June 2026."""
    return datetime(2026, 6, day, hour, minute, tzinfo=BERLIN)


def fresh(tmp_path: Path) -> Sim:
    """Brand-new simulator on scratch state, car plugged in."""
    sim = Sim.load(tmp_path / "wallbox.json", now=at(1, 0))
    sim.plug()
    return sim


def test_plug_unplug_cycle(tmp_path: Path) -> None:
    sim = Sim.load(tmp_path / "wallbox.json", now=at(1, 0))
    assert sim.status()["plugged"] is False
    sim.plug()
    assert sim.status()["plugged"] is True
    sim.unplug()
    status = sim.status()
    assert status["plugged"] is False
    assert status["charging"] is False


def test_start_requires_plugged_car(tmp_path: Path) -> None:
    sim = Sim.load(tmp_path / "wallbox.json", now=at(1, 0))
    with pytest.raises(SimError, match="plugged"):
        sim.start_now(11.0)


def test_start_caps_at_hardware_max(tmp_path: Path) -> None:
    sim = fresh(tmp_path)
    with pytest.raises(SimError, match="22"):
        sim.start_now(23.0)
    assert HARDWARE_MAX_KW == 22.0


def test_manual_charge_integrates_energy(tmp_path: Path) -> None:
    sim = fresh(tmp_path)
    sim.start_now(11.0)
    sim.advance_clock(60)
    status = sim.status()
    assert status["charging"] is True
    assert status["power_kw"] == 11.0
    assert status["session_kwh"] == 11.0
    assert status["total_kwh"] == 11.0
    sim.stop_now()
    stopped = sim.status()
    assert stopped["charging"] is False
    assert stopped["power_kw"] == 0.0
    assert stopped["session_kwh"] == 0.0
    assert stopped["total_kwh"] == 11.0


def test_program_runs_only_inside_its_window(tmp_path: Path) -> None:
    sim = fresh(tmp_path)
    sim.program_charge(at(1, 2).isoformat(), at(1, 4).isoformat(), 11.0)
    sim.advance_clock(60)
    assert sim.status()["charging"] is False
    sim.advance_clock(60)
    assert sim.status()["charging"] is True
    sim.advance_clock(120)
    status = sim.status()
    assert status["charging"] is False
    assert status["session_kwh"] == 22.0


def test_program_boundary_splits_energy(tmp_path: Path) -> None:
    sim = fresh(tmp_path)
    sim.program_charge(at(1, 2).isoformat(), at(1, 4).isoformat(), 10.0)
    sim.advance_clock(180)
    status = sim.status()
    assert status["session_kwh"] == 10.0


def test_program_rejects_bad_windows(tmp_path: Path) -> None:
    sim = fresh(tmp_path)
    with pytest.raises(SimError, match="end"):
        sim.program_charge(at(1, 4).isoformat(), at(1, 2).isoformat(), 11.0)
    with pytest.raises(SimError, match="22"):
        sim.program_charge(at(1, 2).isoformat(), at(1, 4).isoformat(), 30.0)
    with pytest.raises(SimError, match="time"):
        sim.program_charge("tomorrow", at(1, 4).isoformat(), 11.0)


def test_unplugged_program_never_charges(tmp_path: Path) -> None:
    sim = Sim.load(tmp_path / "wallbox.json", now=at(1, 0))
    sim.program_charge(at(1, 0).isoformat(), at(1, 4).isoformat(), 11.0)
    sim.advance_clock(240)
    assert sim.status()["session_kwh"] == 0.0


def test_state_survives_reload(tmp_path: Path) -> None:
    path = tmp_path / "wallbox.json"
    sim = Sim.load(path, now=at(1, 0))
    sim.plug()
    sim.start_now(11.0)
    sim.advance_clock(30)
    again = Sim.load(path, now=at(1, 12))
    status = again.status()
    assert status["plugged"] is True
    assert status["charging"] is True
    assert status["session_kwh"] == 5.5
    assert status["sim_now"] == at(1, 0, 30).isoformat()


def test_advance_caps_at_one_day(tmp_path: Path) -> None:
    sim = fresh(tmp_path)
    with pytest.raises(SimError, match="24 hours"):
        sim.advance_clock(24 * 60 + 1)
    with pytest.raises(SimError, match="positive"):
        sim.advance_clock(0)
