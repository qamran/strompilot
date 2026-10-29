"""Worker nodes: extraction, optimization, narration, review."""

import json
from typing import Any

from pydantic import ValidationError

from strompilot.lifeplan.errors import LifeplanError
from strompilot.lifeplan.extract import analyze
from strompilot.lifeplan.loaders import LoadedPrices, PriceLoader
from strompilot.lifeplan.narrate import narrate
from strompilot.lifeplan.optimize import optimize
from strompilot.lifeplan.schemas import (
    HouseholdConstraints,
    ScheduledSlot,
)
from strompilot.llm.client import LOW_EFFORT, MINIMAL_EFFORT
from strompilot.llm.types import ChatRouter, LlmError, Message

from .guards import approval_granted, audit_event, review_cap_reached
from .state import CitationState, CriticVerdict, PlanState, PriceBarState, Slot

# Budgets cover thinking plus the answer: a one-word reply costs about
# 50 completion tokens, and trivial JSON costs about 230 (live probes).
PERCEIVE_TOKENS = 100
CRITIC_TOKENS = 1000

DETERMINISTIC = "deterministic"


def _attributed(state: PlanState, block: str, model: str) -> dict[str, str]:
    """Merge one block's model attribution into the state's record."""
    return {**state.get("attribution", {}), block: model}


def _format_schedule(state: PlanState) -> str:
    """Render the draft schedule as plain lines."""
    lines = []
    for slot in state.get("schedule", []):
        line = f"- {slot['device']}: {slot['start']} bis {slot['end']}"
        if "cost_eur" in slot:
            line += f" ({slot['cost_eur']:.2f} Euro)"
        line += f" ({slot['reason']})"
        lines.append(line)
    return "\n".join(lines) if lines else "noch kein Plan"


def _read_constraints(state: PlanState, node: str) -> HouseholdConstraints:
    """Validate the state's constraints, failing loudly without them."""
    raw = state.get("constraints")
    if raw is None:
        raise LifeplanError(f"{node} needs constraints")
    try:
        return HouseholdConstraints.model_validate(raw)
    except ValidationError as exc:
        raise LifeplanError(f"{node} needs constraints: {exc}") from exc


def perceive_node(state: PlanState, router: ChatRouter) -> PlanState:
    """Check the request is a planning request, else end gracefully."""
    result = router.chat(
        "supervisor",
        [
            Message(
                role="system",
                content="Reply with exactly one word: plan when the "
                "request asks for household power planning, else other.",
            ),
            Message(role="user", content=state.get("request", "")),
        ],
        PERCEIVE_TOKENS,
        MINIMAL_EFFORT,
    )
    first_word = result.content.strip().lower().split(" ", 1)[0]
    intent = "plan" if first_word == "plan" else "other"
    return PlanState(
        intent=intent,
        attribution=_attributed(state, "intent", result.model),
        audit=[audit_event("perceive", f"intent={intent}")],
    )


def analyst_node(state: PlanState, router: ChatRouter) -> PlanState:
    """Extract price facts plus hard household constraints."""
    analysis = analyze(state.get("request", ""), router)
    attribution = _attributed(state, "analysis", analysis.model)
    attribution["constraints"] = analysis.model
    return PlanState(
        analysis=analysis.facts,
        constraints=analysis.constraints.model_dump(),
        attribution=attribution,
        audit=[
            audit_event(
                "analyst",
                f"{len(analysis.facts)} facts, "
                f"{len(analysis.constraints.devices)} devices",
            )
        ],
    )


def scheduler_node(state: PlanState, price_loader: PriceLoader) -> PlanState:
    """Place every device into its cheapest feasible hours."""
    constraints = _read_constraints(state, "scheduler")
    loaded: LoadedPrices = price_loader()
    plan = optimize(constraints, loaded.bars)
    schedule = [
        Slot(
            device=slot.device,
            start=slot.start,
            end=slot.end,
            reason=slot.reason,
            energy_kwh=slot.energy_kwh,
            price_ct_kwh=slot.price_ct_kwh,
            cost_eur=slot.cost_eur,
        )
        for slot in plan.slots
    ]
    prices = [
        PriceBarState(hour=bar.hour, price_ct_kwh=bar.price_ct_kwh, source=bar.source)
        for bar in loaded.bars
    ]
    return PlanState(
        schedule=schedule,
        unscheduled=plan.unscheduled,
        total_cost_eur=plan.total_cost_eur,
        prices=prices,
        price_source=loaded.source,
        attribution=_attributed(state, "schedule", DETERMINISTIC),
        audit=[
            audit_event(
                "scheduler",
                f"{len(schedule)} slots, "
                f"{plan.total_cost_eur:.2f} Euro, "
                f"{len(plan.unscheduled)} gaps",
            )
        ],
    )


def explainer_node(state: PlanState, router: ChatRouter) -> PlanState:
    """Narrate the priced schedule with citations and checks."""
    constraints = HouseholdConstraints.model_validate(state.get("constraints", {}))
    try:
        slots = [
            ScheduledSlot.model_validate(dict(slot))
            for slot in state.get("schedule", [])
        ]
    except ValidationError as exc:
        raise LifeplanError(f"explainer needs priced slots: {exc}") from exc
    narration, model = narrate(
        slots,
        state.get("total_cost_eur", 0.0),
        constraints,
        state.get("unscheduled", []),
        state.get("price_source", "unknown"),
        router,
    )
    citations = [
        CitationState(
            claim=citation.claim,
            source=citation.source,
            detail=citation.detail,
        )
        for citation in narration.citations
    ]
    return PlanState(
        narration=narration.text,
        citations=citations,
        violations=narration.violations,
        attribution=_attributed(state, "narration", model),
        audit=[
            audit_event(
                "explainer",
                f"{len(citations)} citations, {len(narration.violations)} violations",
            )
        ],
    )


def _parse_verdict(content: str) -> CriticVerdict:
    """Parse the critic's JSON verdict, strictly."""
    try:
        raw = json.loads(content)
    except ValueError as exc:
        raise LlmError("critic returned invalid JSON") from exc
    if not isinstance(raw, dict):
        raise LlmError("critic returned invalid JSON")
    values: dict[str, Any] = raw
    approved = values.get("approved")
    notes = values.get("notes")
    if not isinstance(approved, bool):
        raise LlmError("critic returned invalid JSON")
    if not isinstance(notes, list) or not all(isinstance(note, str) for note in notes):
        raise LlmError("critic returned invalid JSON")
    return CriticVerdict(approved=approved, notes=list(notes))


def critic_node(state: PlanState, router: ChatRouter) -> PlanState:
    """Judge the draft, counting review cycles toward the cap."""
    parts = [
        f"Request: {state.get('request', '')}",
        f"Schedule:\n{_format_schedule(state)}",
        f"Narration: {state.get('narration', '')}",
    ]
    if state.get("violations"):
        lines = "\n".join(f"- {item}" for item in state["violations"])
        parts.append(f"Faithfulness violations:\n{lines}")
    if state.get("unscheduled"):
        lines = "\n".join(f"- {item}" for item in state["unscheduled"])
        parts.append(f"Unscheduled devices:\n{lines}")
    result = router.chat(
        "critic",
        [
            Message(
                role="system",
                content="Judge the draft narration against the computed "
                "schedule. The schedule is final: it already places every "
                "device into its cheapest feasible hours, so never veto "
                "device times, prices, or costs. Approve when every "
                "scheduled device appears with correct HH:MM times, every "
                "cost matches, unscheduled devices are mentioned when "
                "listed, and no violation stands. Veto only narration "
                "defects, naming the exact broken sentence in notes. "
                "Reply with JSON only: approved boolean plus notes list "
                "of strings.",
            ),
            Message(role="user", content="\n\n".join(parts)),
        ],
        CRITIC_TOKENS,
        LOW_EFFORT,
    )
    verdict = _parse_verdict(result.content)
    iterations = state.get("iterations", 0) + 1
    update = PlanState(
        verdict=verdict,
        iterations=iterations,
        attribution=_attributed(state, "verdict", result.model),
        audit=[
            audit_event(
                "critic",
                "approved" if verdict["approved"] else "veto",
            )
        ],
    )
    if not verdict["approved"] and review_cap_reached(iterations):
        update["error"] = "review cap reached"
    return update


def publish_node(state: PlanState) -> PlanState:
    """Publish the approved plan, failing closed without approval."""
    if not approval_granted(state.get("approval", "pending")):
        return PlanState(
            error="publish blocked: approval pending",
            audit=[audit_event("publish", "blocked: approval pending")],
        )
    return PlanState(
        published=True,
        audit=[audit_event("publish", "plan published")],
    )
