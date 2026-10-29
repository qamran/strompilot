"""Routing goldens for the supervisor graph."""

from strompilot.agents.state import CriticVerdict, PlanState
from strompilot.agents.supervisor import route_next, route_perceive


def test_perceive_routes_planning_to_analyst() -> None:
    assert route_perceive(PlanState(request="x", intent="plan")) == "analyst"


def test_perceive_ends_other_intent() -> None:
    assert route_perceive(PlanState(request="x", intent="other")) == "end"


def test_perceive_fails_closed_without_intent() -> None:
    assert route_perceive(PlanState(request="x")) == "end"


def test_approved_verdict_routes_to_publish() -> None:
    state = PlanState(request="x", verdict=CriticVerdict(approved=True, notes=[]))
    assert route_next(state) == "publish"


def test_veto_routes_back_to_scheduler() -> None:
    state = PlanState(
        request="x",
        verdict=CriticVerdict(approved=False, notes=["beleg fehlt"]),
        iterations=1,
    )
    assert route_next(state) == "scheduler"


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
