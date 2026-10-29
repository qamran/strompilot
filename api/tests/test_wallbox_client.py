"""Tests for the wallbox MCP client and policy gates."""

from datetime import date
from pathlib import Path

import pytest

from strompilot.wallbox.client import WallboxClient, WallboxError, WallboxStatus
from strompilot.wallbox.policy import ChargePolicy, authorize


def test_status_parses_payload() -> None:
    def fake_caller(tool: str, args: dict[str, object]) -> dict[str, object]:
        assert tool == "get_status"
        assert args == {}
        return {
            "plugged": True,
            "charging": True,
            "power_kw": 11.0,
            "max_kw": 11.0,
            "session_kwh": 5.5,
            "total_kwh": 5.5,
            "sim_now": "2026-06-01T00:30:00+02:00",
            "program": None,
        }

    status = WallboxClient(caller=fake_caller).status()
    assert status == WallboxStatus(
        plugged=True,
        charging=True,
        power_kw=11.0,
        max_kw=11.0,
        session_kwh=5.5,
        total_kwh=5.5,
        sim_now="2026-06-01T00:30:00+02:00",
        program=None,
    )


def test_program_window_builds_overnight_iso() -> None:
    seen: dict[str, object] = {}

    def fake_caller(tool: str, args: dict[str, object]) -> dict[str, object]:
        seen["tool"] = tool
        seen["args"] = args
        return _idle_status()

    WallboxClient(caller=fake_caller).program_window(
        date(2026, 6, 1), "22:00", "06:00", 11.0
    )
    assert seen["tool"] == "program_charge"
    args = seen["args"]
    assert isinstance(args, dict)
    assert args["start_iso"] == "2026-06-01T22:00:00+02:00"
    assert args["end_iso"] == "2026-06-02T06:00:00+02:00"
    assert args["max_kw"] == 11.0


def test_program_window_rejects_bad_clock() -> None:
    client = WallboxClient(caller=_boom)
    with pytest.raises(WallboxError, match="clock"):
        client.program_window(date(2026, 6, 1), "25:00", "06:00", 11.0)


def _boom(tool: str, args: dict[str, object]) -> dict[str, object]:
    raise AssertionError("caller must not run")


def _idle_status() -> dict[str, object]:
    return {
        "plugged": True,
        "charging": False,
        "power_kw": 0.0,
        "max_kw": 0.0,
        "session_kwh": 0.0,
        "total_kwh": 0.0,
        "sim_now": "2026-06-01T00:00:00+02:00",
        "program": None,
    }


def test_caller_errors_pass_through() -> None:
    def failing(tool: str, args: dict[str, object]) -> dict[str, object]:
        del tool, args
        raise WallboxError("sim refused: car is not plugged in")

    with pytest.raises(WallboxError, match="not plugged"):
        WallboxClient(caller=failing).start(11.0)


def test_advance_and_stop_forward() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_caller(tool: str, args: dict[str, object]) -> dict[str, object]:
        calls.append((tool, args))
        return _idle_status()

    client = WallboxClient(caller=fake_caller)
    client.plug()
    client.advance(30)
    client.stop()
    assert [name for name, _ in calls] == ["plug", "advance_clock", "stop_now"]
    assert calls[1][1] == {"minutes": 30}


def test_policy_allows_sane_sim_charge() -> None:
    policy = ChargePolicy(max_kw=11.0, hardware="simulated")
    decision = authorize(
        policy, "2026-06-01T02:00:00+02:00", "2026-06-02T04:00:00+02:00", 11.0
    )
    assert (decision.allowed, decision.reason) == (True, "ok")


def test_policy_blocks_over_power() -> None:
    decision = authorize(
        ChargePolicy(max_kw=4.0),
        "2026-06-01T02:00:00+02:00",
        "2026-06-01T04:00:00+02:00",
        11.0,
    )
    assert decision.allowed is False
    assert "4.0" in decision.reason


def test_policy_blocks_bad_windows() -> None:
    policy = ChargePolicy()
    flipped = authorize(
        policy, "2026-06-01T04:00:00+02:00", "2026-06-01T02:00:00+02:00", 11.0
    )
    assert flipped.allowed is False
    garbage = authorize(policy, "soon", "later", 11.0)
    assert garbage.allowed is False


def test_policy_blocks_real_hardware() -> None:
    decision = authorize(
        ChargePolicy(hardware="real"),
        "2026-06-01T02:00:00+02:00",
        "2026-06-01T04:00:00+02:00",
        11.0,
    )
    assert decision.allowed is False
    assert "approval" in decision.reason


def test_round_trip_through_real_server(tmp_path: Path) -> None:
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    berlin = ZoneInfo("Europe/Berlin")
    now = datetime.now(berlin).replace(minute=0, second=0, microsecond=0)
    start = now.isoformat()
    end = (now + timedelta(hours=4)).isoformat()
    client = WallboxClient(state_path=tmp_path / "wallbox.json")
    assert client.status().plugged is False
    plugged = client.plug()
    assert plugged.charging is False
    client.program(start, end, 11.0)
    client.advance(60)
    charged = client.status()
    assert charged.charging is True
    assert charged.session_kwh == 11.0
    assert charged.total_kwh == 11.0
    with pytest.raises(WallboxError, match="after start"):
        client.program(end, start, 11.0)
