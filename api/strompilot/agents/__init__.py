"""Agent core: typed state, router, guards, workers, graph."""

from strompilot.llm.types import ChatRouter

from .guards import GuardError
from .router import ModelRouter, SpendEntry
from .state import (
    Approval,
    CitationState,
    CriticVerdict,
    PlanState,
    PriceBarState,
    Slot,
)
from .supervisor import build_graph, route_next, route_perceive
from .workers import (
    analyst_node,
    critic_node,
    explainer_node,
    perceive_node,
    publish_node,
    scheduler_node,
)

__all__ = [
    "Approval",
    "ChatRouter",
    "CitationState",
    "CriticVerdict",
    "GuardError",
    "ModelRouter",
    "PlanState",
    "PriceBarState",
    "Slot",
    "SpendEntry",
    "analyst_node",
    "build_graph",
    "critic_node",
    "explainer_node",
    "perceive_node",
    "publish_node",
    "route_next",
    "route_perceive",
    "scheduler_node",
]
