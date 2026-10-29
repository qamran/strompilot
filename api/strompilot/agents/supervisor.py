"""Supervisor graph: perceive, delegate, review, publish."""

from functools import partial
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from strompilot.lifeplan.loaders import PriceLoader
from strompilot.llm.types import ChatRouter

from .state import PlanState
from .workers import (
    analyst_node,
    critic_node,
    explainer_node,
    perceive_node,
    publish_node,
    scheduler_node,
)


def route_perceive(state: PlanState) -> Literal["analyst", "end"]:
    """Send planning requests to the analyst, ending anything else."""
    if state.get("intent") == "plan":
        return "analyst"
    return "end"


def route_next(state: PlanState) -> Literal["scheduler", "publish", "end"]:
    """Route after the critic: loop on veto, publish on approval."""
    if state.get("error"):
        return "end"
    verdict = state.get("verdict")
    if verdict is None:
        return "end"
    if verdict["approved"]:
        return "publish"
    return "scheduler"


def build_graph(
    router: ChatRouter, price_loader: PriceLoader
) -> CompiledStateGraph[PlanState, None, PlanState, PlanState]:
    """Compile the supervisor graph with one router for every worker."""
    graph = StateGraph(PlanState)
    graph.add_node("perceive", partial(perceive_node, router=router))
    graph.add_node("analyst", partial(analyst_node, router=router))
    graph.add_node("scheduler", partial(scheduler_node, price_loader=price_loader))
    graph.add_node("explainer", partial(explainer_node, router=router))
    graph.add_node("critic", partial(critic_node, router=router))
    graph.add_node("publish", publish_node)
    graph.add_edge(START, "perceive")
    graph.add_conditional_edges(
        "perceive", route_perceive, {"analyst": "analyst", "end": END}
    )
    graph.add_edge("analyst", "scheduler")
    graph.add_edge("scheduler", "explainer")
    graph.add_edge("explainer", "critic")
    graph.add_conditional_edges(
        "critic",
        route_next,
        {"scheduler": "scheduler", "publish": "publish", "end": END},
    )
    graph.add_edge("publish", END)
    return graph.compile()
