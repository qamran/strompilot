"""Worker nodes: thin SP-04 wiring with simple first prompts."""

import json
from typing import Any

from strompilot.llm.client import LOW_EFFORT, MINIMAL_EFFORT
from strompilot.llm.types import LlmError, Message

from .guards import approval_granted, audit_event, review_cap_reached
from .router import ChatRouter
from .state import CriticVerdict, PlanState, Slot

# Budgets cover thinking plus the answer: a one-word reply costs about
# 50 completion tokens, and trivial JSON costs about 230 (live probes).
PERCEIVE_TOKENS = 100
ANALYST_TOKENS = 1000
SCHEDULER_TOKENS = 1200
EXPLAINER_TOKENS = 1500
CRITIC_TOKENS = 1000

_SLOT_KEYS = ("device", "start", "end", "reason")


def _attributed(state: PlanState, block: str, model: str) -> dict[str, str]:
    """Merge one block's model attribution into the state's record."""
    return {**state.get("attribution", {}), block: model}


def _format_schedule(state: PlanState) -> str:
    """Render the draft schedule as plain lines."""
    lines = [
        f"- {slot['device']}: {slot['start']} bis {slot['end']} ({slot['reason']})"
        for slot in state.get("schedule", [])
    ]
    return "\n".join(lines) if lines else "noch kein Plan"


def _scheduler_brief(state: PlanState) -> str:
    """Build the scheduler brief from request, facts, and review notes."""
    parts = [f"Request: {state.get('request', '')}"]
    facts = state.get("analysis", [])
    if facts:
        parts.append("Price facts:\n" + "\n".join(f"- {fact}" for fact in facts))
    verdict = state.get("verdict")
    if verdict and verdict["notes"]:
        notes = "\n".join(f"- {note}" for note in verdict["notes"])
        parts.append(f"Previous review notes, fix every one:\n{notes}")
    return "\n\n".join(parts)


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
    """Collect price facts about the requested window."""
    result = router.chat(
        "analyst",
        [
            Message(
                role="system",
                content="List short price facts for the planning "
                "request, one per line.",
            ),
            Message(role="user", content=state.get("request", "")),
        ],
        ANALYST_TOKENS,
        LOW_EFFORT,
    )
    facts = [line.strip() for line in result.content.splitlines() if line.strip()]
    return PlanState(
        analysis=facts,
        attribution=_attributed(state, "analysis", result.model),
        audit=[audit_event("analyst", f"{len(facts)} facts")],
    )


def _parse_slots(content: str) -> list[Slot]:
    """Parse the scheduler's JSON slot list, strictly."""
    try:
        raw = json.loads(content)
    except ValueError as exc:
        raise LlmError("scheduler returned invalid JSON") from exc
    if not isinstance(raw, list):
        raise LlmError("scheduler returned invalid JSON")
    slots: list[Slot] = []
    for item in raw:
        if not isinstance(item, dict):
            raise LlmError("scheduler returned invalid JSON")
        values: dict[str, Any] = item
        if not all(
            key in values and isinstance(values[key], str) for key in _SLOT_KEYS
        ):
            raise LlmError("scheduler returned invalid JSON")
        slots.append(
            Slot(
                device=values["device"],
                start=values["start"],
                end=values["end"],
                reason=values["reason"],
            )
        )
    return slots


def scheduler_node(state: PlanState, router: ChatRouter) -> PlanState:
    """Draft the device schedule as a JSON slot list."""
    result = router.chat(
        "scheduler",
        [
            Message(
                role="system",
                content="Reply with a JSON list of schedule slots only. "
                "Each slot has device, start, end, and reason strings.",
            ),
            Message(role="user", content=_scheduler_brief(state)),
        ],
        SCHEDULER_TOKENS,
        LOW_EFFORT,
    )
    slots = _parse_slots(result.content)
    return PlanState(
        schedule=slots,
        attribution=_attributed(state, "schedule", result.model),
        audit=[audit_event("scheduler", f"{len(slots)} slots")],
    )


def explainer_node(state: PlanState, router: ChatRouter) -> PlanState:
    """Narrate the draft schedule in plain words."""
    brief = (
        f"Request: {state.get('request', '')}\n\nSchedule:\n{_format_schedule(state)}"
    )
    result = router.chat(
        "explainer",
        [
            Message(
                role="system",
                content="Explain the schedule simply, in the household's language.",
            ),
            Message(role="user", content=brief),
        ],
        EXPLAINER_TOKENS,
        LOW_EFFORT,
    )
    return PlanState(
        narration=result.content,
        attribution=_attributed(state, "narration", result.model),
        audit=[audit_event("explainer", "narration written")],
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
    brief = (
        f"Request: {state.get('request', '')}\n\n"
        f"Schedule:\n{_format_schedule(state)}\n\n"
        f"Narration: {state.get('narration', '')}"
    )
    result = router.chat(
        "critic",
        [
            Message(
                role="system",
                content="Judge the draft schedule against the request. "
                "Approve when every requested device has a slot and the "
                "narration matches the schedule. Reply with JSON only: "
                "approved boolean plus notes list of strings.",
            ),
            Message(role="user", content=brief),
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
