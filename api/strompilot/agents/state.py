"""Typed graph state shared by every worker."""

import operator
from typing import Annotated, Any, Literal, NotRequired, TypedDict

Approval = Literal["pending", "approved", "rejected"]


class Slot(TypedDict):
    """One scheduled device run with its reason and priced cost."""

    device: str
    start: str
    end: str
    reason: str
    energy_kwh: NotRequired[float]
    price_ct_kwh: NotRequired[float]
    cost_eur: NotRequired[float]


class PriceBarState(TypedDict):
    """One priced Berlin hour carried in the state."""

    hour: int
    price_ct_kwh: float
    source: str


class CitationState(TypedDict):
    """One sourced claim backing the narration."""

    claim: str
    source: str
    detail: str


class CriticVerdict(TypedDict):
    """The critic's judgment on the current draft."""

    approved: bool
    notes: list[str]


class PlanState(TypedDict, total=False):
    """Everything the graph knows about one planning run."""

    request: str
    household_id: str
    intent: str
    analysis: list[str]
    constraints: dict[str, Any]
    prices: list[PriceBarState]
    price_source: str
    schedule: list[Slot]
    unscheduled: list[str]
    total_cost_eur: float
    narration: str
    citations: list[CitationState]
    violations: list[str]
    verdict: CriticVerdict | None
    iterations: int
    approval: Approval
    published: bool
    error: str | None
    attribution: dict[str, str]
    audit: Annotated[list[str], operator.add]
