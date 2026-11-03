"""Routing goldens for the supervisor graph."""

from strompilot.agents.state import CriticVerdict, PlanState
from strompilot.agents.supervisor import route_next, route_perceive, route_schedule


def test_perceive_routes_planning_to_analyst() -> None:
    assert route_perceive(PlanState(request="x", intent="plan")) == "analyst"


def test_perceive_ends_other_intent() -> None:
    assert route_perceive(PlanState(request="x", intent="other")) == "end"


def test_perceive_fails_closed_without_intent() -> None:
    assert route_perceive(PlanState(request="x")) == "end"


def test_approved_verdict_routes_to_publish() -> None:
    state = PlanState(request="x", verdict=CriticVerdict(approved=True, notes=[]))
    assert route_next(state) == "publish"


def test_veto_routes_back_to_analyst() -> None:
    state = PlanState(
        request="x",
        verdict=CriticVerdict(approved=False, notes=["beleg fehlt"]),
        iterations=1,
    )
    assert route_next(state) == "analyst"


def test_error_routes_to_end() -> None:
    state = PlanState(
        request="x",
        verdict=CriticVerdict(approved=False, notes=[]),
        iterations=3,
        error="review cap reached",
    )
    assert route_next(state) == "end"


def test_error_beats_approval() -> None:
    state = PlanState(
        request="x",
        verdict=CriticVerdict(approved=True, notes=[]),
        error="publish blocked: approval pending",
    )
    assert route_next(state) == "end"


def test_missing_verdict_fails_closed() -> None:
    assert route_next(PlanState(request="x")) == "end"


def test_scheduler_error_ends_run() -> None:
    assert route_schedule(PlanState(request="x", error="nothing to schedule")) == "end"


def test_scheduler_clean_explains() -> None:
    assert route_schedule(PlanState(request="x")) == "explainer"
