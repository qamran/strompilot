"""Tests for the guard predicates."""

from strompilot.agents.guards import (
    approval_granted,
    audit_event,
    cost_rail_hit,
    has_stall,
    review_cap_reached,
)
from strompilot.agents.router import SpendEntry


def test_review_cap_reached() -> None:
    assert not review_cap_reached(0)
    assert not review_cap_reached(2)
    assert review_cap_reached(3)
    assert review_cap_reached(9)


def test_has_stall() -> None:
    assert has_stall(["a", "a", "a"])
    assert has_stall(["x", "a", "a", "a"])
    assert not has_stall(["a", "a", "b"])
    assert not has_stall(["a", "b", "a"])
    assert not has_stall(["a", "a"])
    assert not has_stall([])


def test_cost_rail_hit() -> None:
    def entry(tokens: int, cost: float | None) -> SpendEntry:
        return SpendEntry(
            worker="analyst",
            requested_model="m",
            actual_model="m",
            input_tokens=tokens,
            output_tokens=0,
            cost_usd=cost,
        )

    assert not cost_rail_hit([entry(100, 0.01)])
    assert not cost_rail_hit([])
    assert cost_rail_hit([entry(1_000_000, None)])
    assert cost_rail_hit([entry(100, 5.00)])
    assert cost_rail_hit([entry(100, None), entry(100, None)] * 2000)


def test_approval_granted() -> None:
    assert approval_granted("approved")
    assert not approval_granted("pending")
    assert not approval_granted("rejected")
    assert not approval_granted("yes please")


def test_audit_event_names_node_and_detail() -> None:
    event = audit_event("critic", "veto: missing citation")
    assert "critic" in event
    assert "veto: missing citation" in event
    assert len(event) > len("critic: veto: missing citation")
