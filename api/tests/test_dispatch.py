"""Tests for wallbox dispatch inside graph runs."""

from strompilot.agents.state import PlanState
from strompilot.agents.supervisor import build_graph
from strompilot.agents.workers import dispatch_node
from strompilot.wallbox.client import WallboxError
from strompilot.wallbox.policy import ChargePolicy
from tests.fakes import (
    FakeRouter,
    FakeWallbox,
    idle_wallbox_status,
    reply,
    stub_loader,
)
from tests.test_graph import APPROVE


def ev_state() -> PlanState:
    """Planning state with one priced E-Auto slot."""
    return PlanState(
        request="lade mein Auto",
        plan_day="2026-06-01",
        approval="approved",
        schedule=[
            {
                "device": "E-Auto",
                "start": "02:00",
                "end": "06:00",
                "reason": "billig",
                "energy_kwh": 44.0,
                "price_ct_kwh": 15.0,
                "cost_eur": 6.60,
            }
        ],
        total_cost_eur=6.60,
    )


def test_dispatch_programs_the_ev_slot() -> None:
    wallbox = FakeWallbox([idle_wallbox_status()])
    update = dispatch_node(ev_state(), wallbox=wallbox)
    assert wallbox.programs == [
        ("2026-06-01T02:00:00+02:00", "2026-06-01T06:00:00+02:00", 11.0)
    ]
    assert update.get("error") is None
    assert any("dispatch" in event for event in update.get("audit", []))


def test_dispatch_without_wallbox_skips() -> None:
    update = dispatch_node(ev_state())
    assert update.get("error") is None
    assert any("no wallbox" in event for event in update.get("audit", []))


def test_dispatch_without_ev_slot_skips() -> None:
    wallbox = FakeWallbox([idle_wallbox_status()])
    state = PlanState(
        request="wasche",
        plan_day="2026-06-01",
        schedule=[
            {
                "device": "Waschmaschine",
                "start": "02:00",
                "end": "04:00",
                "reason": "billig",
            }
        ],
    )
    update = dispatch_node(state, wallbox=wallbox)
    assert wallbox.programs == []
    assert any("no E-Auto" in event for event in update.get("audit", []))


def test_policy_deny_blocks_with_error() -> None:
    wallbox = FakeWallbox([idle_wallbox_status()])
    update = dispatch_node(ev_state(), wallbox=wallbox, policy=ChargePolicy(max_kw=4.0))
    assert (
        update.get("error") == "dispatch blocked: power 11.0 kW exceeds policy 4.0 kW"
    )
    assert wallbox.programs == []


def test_wallbox_error_blocks_with_error() -> None:
    wallbox = FakeWallbox([WallboxError("sim down")])
    update = dispatch_node(ev_state(), wallbox=wallbox)
    assert update.get("error") == "dispatch failed: sim down"


def test_graph_dispatches_ev_plan() -> None:
    from strompilot.llm.client import SPARK_OPEN_MODEL

    router = FakeRouter(
        {
            "supervisor": [reply("plan")],
            "analyst": [reply(_EV_ANALYST_JSON)],
            "explainer": [reply(_EV_NARRATION, SPARK_OPEN_MODEL)] * 2,
            "critic": [reply(APPROVE)],
        }
    )
    wallbox = FakeWallbox([idle_wallbox_status()])
    graph = build_graph(router, stub_loader, wallbox=wallbox)
    final = graph.invoke(
        {
            "request": "lade mein Auto",
            "approval": "approved",
            "plan_day": "2026-06-01",
        }
    )
    assert final["published"] is True
    assert len(wallbox.programs) == 1
    start, end, power = wallbox.programs[0]
    assert (start, end, power) == (
        "2026-06-01T00:00:00+02:00",
        "2026-06-01T04:00:00+02:00",
        11.0,
    )


def test_graph_blocked_dispatch_skips_publish() -> None:
    from strompilot.llm.client import SPARK_OPEN_MODEL

    router = FakeRouter(
        {
            "supervisor": [reply("plan")],
            "analyst": [reply(_EV_ANALYST_JSON)],
            "explainer": [reply(_EV_NARRATION, SPARK_OPEN_MODEL)] * 2,
            "critic": [reply(APPROVE)],
        }
    )
    wallbox = FakeWallbox([idle_wallbox_status()])
    graph = build_graph(
        router, stub_loader, wallbox=wallbox, policy=ChargePolicy(max_kw=4.0)
    )
    final = graph.invoke(
        {
            "request": "lade mein Auto",
            "approval": "approved",
            "plan_day": "2026-06-01",
        }
    )
    assert final.get("published", False) is False
    assert final["error"] == "dispatch blocked: power 11.0 kW exceeds policy 4.0 kW"


_EV_ANALYST_JSON = """{"facts": ["billig nachts"],
"devices": [
{"device": "E-Auto", "power_kw": 11.0, "duration_h": 4.0,
"earliest": "22:00", "latest": "06:00", "shiftable": true}
],
"notes": ""}"""

_EV_NARRATION = (
    "Das E-Auto lädt von 00:00 bis 04:00 Uhr und kostet 9,90 €. "
    "Die Gesamtkosten betragen 9,90 €."
)
