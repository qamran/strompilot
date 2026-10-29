"""Typed graph state shared by every worker."""

import operator
from typing import Annotated, Literal, TypedDict

Approval = Literal["pending", "approved", "rejected"]


class Slot(TypedDict):
    """One scheduled device run with its reason."""

    device: str
    start: str
    end: str
    reason: str


class CriticVerdict(TypedDict):
    """The critic's judgment on the current draft."""

    approved: bool
    notes: list[str]


class PlanState(TypedDict, total=False):
    """Everything the graph knows about one planning run."""

    request: str
    intent: str
    analysis: list[str]
    schedule: list[Slot]
    narration: str
    verdict: CriticVerdict | None
    iterations: int
    approval: Approval
    published: bool
    error: str | None
    attribution: dict[str, str]
    audit: Annotated[list[str], operator.add]
