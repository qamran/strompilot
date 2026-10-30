"""Cited narration: Baseten drafts, deterministic citations and checks."""

import re

from strompilot.llm.client import LOW_EFFORT
from strompilot.llm.types import ChatRouter, Message

from .schemas import (
    Citation,
    HouseholdConstraints,
    Narration,
    ScheduledSlot,
)

NARRATE_TOKENS = 1500

_TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_MONEY_RE = re.compile(r"(\d+[.,]\d{2})\s*(€|Euro|euro|EUR|ct|Cent|cent)(?!\w)")
_FOLD = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
_EURO_UNITS = {"€", "Euro", "euro", "EUR"}
_EURO_TOLERANCE = 0.06
_CT_TOLERANCE = 0.6

_SYSTEM = """You are Strompilot, a friendly German energy advisor for
households on dynamic tariffs. Turn the plan bullets into a short German
household message of 4-8 sentences.
Rules:
- Name every device with its running time in HH:MM format and its cost
in Euro with 2 decimals.
- State the total cost in Euro with 2 decimals.
- Mention unscheduled devices when listed, with one short reason each.
- Add no times, prices, costs, or devices beyond the bullets.
- Reply in German, plain words, no markdown headers."""

_EXAMPLE_BULLETS = """- Waschmaschine: 02:00 bis 04:00, 4,0 kWh,
Durchschnitt 15,00 ct/kWh, Kosten 0,60 Euro.
Gesamtkosten: 0,60 Euro."""
_EXAMPLE_REPLY = (
    "Gute Nachricht: Die Waschmaschine läuft von 02:00 bis 04:00 Uhr, "
    "wenn der Strom mit 15,00 ct pro kWh am billigsten ist. "
    "Die 4,0 kWh kosten dich 0,60 Euro. "
    "Die Gesamtkosten für morgen betragen 0,60 Euro."
)


def _euro(value: float) -> str:
    """Format Euro with German decimal comma."""
    return f"{value:.2f}".replace(".", ",")


def _brief(
    slots: list[ScheduledSlot],
    total_cost_eur: float,
    unscheduled: list[str],
) -> str:
    """Render the deterministic plan bullets for the draft prompt."""
    lines = [
        f"- {slot.device}: {slot.start} bis {slot.end}, "
        f"{_euro(slot.energy_kwh)} kWh, "
        f"Durchschnitt {_euro(slot.price_ct_kwh)} ct/kWh, "
        f"Kosten {_euro(slot.cost_eur)} Euro."
        for slot in slots
    ]
    lines.append(f"Gesamtkosten: {_euro(total_cost_eur)} Euro.")
    for gap in unscheduled:
        lines.append(f"Nicht planbar: {gap}.")
    return "\n".join(lines)


def build_citations(
    slots: list[ScheduledSlot],
    total_cost_eur: float,
    constraints: HouseholdConstraints,
    unscheduled: list[str],
    price_source: str,
) -> list[Citation]:
    """Cite every slot, the total, every window, and every gap."""
    citations = [
        Citation(
            claim=f"{slot.device} läuft {slot.start} bis {slot.end}",
            source="day-ahead",
            detail=(f"Ø {_euro(slot.price_ct_kwh)} ct/kWh all-in ({price_source})"),
        )
        for slot in slots
    ]
    citations.append(
        Citation(
            claim=f"Gesamtkosten {_euro(total_cost_eur)} Euro",
            source="tariff",
            detail="all-in inkl. Umlagen und MwSt",
        )
    )
    for device in constraints.devices:
        if device.shiftable:
            claim = f"{device.device} flexibel {device.earliest} bis {device.latest}"
        else:
            claim = f"{device.device} läuft zu fester Zeit"
        citations.append(
            Citation(
                claim=claim,
                source="household",
                detail="Zeitfenster aus Haushaltsangabe",
            )
        )
    for gap in unscheduled:
        citations.append(
            Citation(
                claim=gap,
                source="planner",
                detail="kein passendes Fenster im Zieltageszeitraum",
            )
        )
    return citations


def _to_minutes(hours: str, minutes: str) -> int:
    """Convert a regex time match to minutes since midnight."""
    return int(hours) * 60 + int(minutes)


def check_faithfulness(
    text: str, slots: list[ScheduledSlot], total_cost_eur: float
) -> list[str]:
    """List every time, amount, or device the plan does not back."""
    violations: list[str] = []
    backed_minutes = {_to_minutes(*slot.start.split(":")) for slot in slots}
    backed_minutes |= {_to_minutes(*slot.end.split(":")) for slot in slots}
    for match in _TIME_RE.finditer(text):
        if _to_minutes(match.group(1), match.group(2)) not in backed_minutes:
            violations.append(f"Uhrzeit {match.group(0)} ohne Planbeleg")
    for match in _MONEY_RE.finditer(text):
        value = float(match.group(1).replace(",", "."))
        if match.group(2) in _EURO_UNITS:
            backed = abs(value - total_cost_eur) <= _EURO_TOLERANCE or any(
                abs(value - slot.cost_eur) <= _EURO_TOLERANCE for slot in slots
            )
        else:
            backed = any(
                abs(value - slot.price_ct_kwh) <= _CT_TOLERANCE for slot in slots
            )
        if not backed:
            violations.append(f"Betrag {match.group(0)} ohne Planbeleg")
    folded = text.lower().translate(_FOLD)
    for slot in slots:
        if slot.device.lower().translate(_FOLD) not in folded:
            violations.append(f"Gerät {slot.device} fehlt im Text")
    return violations


def narrate(
    slots: list[ScheduledSlot],
    total_cost_eur: float,
    constraints: HouseholdConstraints,
    unscheduled: list[str],
    price_source: str,
    router: ChatRouter,
    system_prompt: str = _SYSTEM,
) -> tuple[Narration, str]:
    """Draft the narration with one repair retry plus citations."""
    brief = _brief(slots, total_cost_eur, unscheduled)
    messages = [
        Message(role="system", content=system_prompt),
        Message(role="user", content=_EXAMPLE_BULLETS),
        Message(role="assistant", content=_EXAMPLE_REPLY),
        Message(role="user", content=brief),
    ]
    result = router.chat("explainer", messages, NARRATE_TOKENS, LOW_EFFORT)
    violations = check_faithfulness(result.content, slots, total_cost_eur)
    if violations:
        repair = router.chat(
            "explainer",
            [
                *messages,
                Message(role="assistant", content=result.content),
                Message(
                    role="user",
                    content="Fix these violations, keep every other "
                    f"sentence: {'; '.join(violations)}",
                ),
            ],
            NARRATE_TOKENS,
            LOW_EFFORT,
        )
        result = repair
        violations = check_faithfulness(result.content, slots, total_cost_eur)
    citations = build_citations(
        slots, total_cost_eur, constraints, unscheduled, price_source
    )
    return Narration(
        text=result.content, citations=citations, violations=violations
    ), result.model
