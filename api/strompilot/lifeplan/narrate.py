"""Cited narration: Baseten drafts, deterministic citations and checks."""

import re
from collections.abc import Sequence

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
_DEVICE_ALIASES = {
    "waschmaschine": ["washing machine", "washer"],
    "geschirrspueler": ["dishwasher", "dish washer"],
    "trockner": ["dryer", "tumble dryer"],
    "e-auto": ["electric car", "e-car", "ev"],
    "eauto": ["electric car", "e-car", "ev"],
    "waermepumpe": ["heat pump"],
    "herd": ["stove", "cooker", "oven"],
    "gefrierschrank": ["freezer"],
}
_EURO_UNITS = {"€", "Euro", "euro", "EUR"}
_EURO_TOLERANCE = 0.06
_CT_TOLERANCE = 0.6

_SYSTEM = {
    "de": """You are Strompilot, a friendly German energy advisor for
households on dynamic tariffs. Turn the plan bullets into a short German
household message, about two sentences per device plus one for the total.
Sound warm and specific, like a text from a friend who read the meter.
Rules:
- Name every device with its running time in HH:MM format and its cost
in Euro with 2 decimals.
- State the total cost in Euro with 2 decimals.
- Mention unscheduled devices when listed, with one short reason each.
- State in words why each device runs at its time (cheapest hours or
fixed household time from the bullet reason); never invent new numbers
for the reason.
- Tie each device's timing to one household fact with
'weil du gesagt hast, …'.
- Add no times, prices, costs, or devices beyond the bullets and facts.
- Reply in German, plain words, no markdown headers.""",
    "en": """You are Strompilot, a friendly energy advisor for
households on dynamic tariffs. Turn the plan bullets into a short English
household message, about two sentences per device plus one for the total.
Sound warm and specific, like a text from a friend who read the meter.
Rules:
- Name every device with its running time in HH:MM format and its cost
in Euro with 2 decimals.
- State the total cost in Euro with 2 decimals.
- Mention unscheduled devices when listed, with one short reason each.
- State in words why each device runs at its time (cheapest hours or
fixed household time from the bullet reason); never invent new numbers
for the reason.
- Tie each device's timing to one household fact with
'because you said …'.
- Add no times, prices, costs, or devices beyond the bullets and facts.
- Reply in English, plain words, no markdown headers.""",
}

_EXAMPLE_BULLETS = {
    "de": """- Waschmaschine: 02:00 bis 04:00, 4,0 kWh,
Durchschnitt 15,00 ct/kWh, Kosten 0,60 Euro.
Gesamtkosten: 0,60 Euro.
Haushaltsangaben:
- du schläfst nach der Nachtschicht tagsüber.""",
    "en": """- Washing machine: 02:00 to 04:00, 4.00 kWh,
average 15.00 ct/kWh, cost 0.60 Euro.
Total cost: 0.60 Euro.
Household facts:
- you sleep during the day after night shifts.""",
}
_EXAMPLE_REPLY = {
    "de": (
        "Gute Nachricht: Die Waschmaschine läuft von 02:00 bis 04:00 Uhr, "
        "wenn der Strom mit 15,00 ct pro kWh am billigsten ist. "
        "Die 4,0 kWh für 0,60 Euro laufen nachts, weil du gesagt hast, "
        "dass du tagsüber schläfst. "
        "Die Gesamtkosten für morgen betragen 0,60 Euro."
    ),
    "en": (
        "Good news: the washing machine runs from 02:00 to 04:00, "
        "when power is cheapest at 15.00 ct per kWh. "
        "The 4.00 kWh for 0.60 Euro run overnight because you said "
        "you sleep during the day. "
        "The total cost for tomorrow is 0.60 Euro."
    ),
}


def _euro(value: float, lang: str) -> str:
    """Format Euro with a decimal comma (de) or point (en)."""
    text = f"{value:.2f}"
    return text.replace(".", ",") if lang == "de" else text


def _brief(
    slots: list[ScheduledSlot],
    total_cost_eur: float,
    unscheduled: list[str],
    lang: str,
    facts: Sequence[str] = (),
) -> str:
    """Render the deterministic plan bullets for the draft prompt."""
    if lang == "en":
        lines = [
            f"- {slot.device}: {slot.start} to {slot.end}, "
            f"{_euro(slot.energy_kwh, lang)} kWh, "
            f"average {_euro(slot.price_ct_kwh, lang)} ct/kWh, "
            f"cost {_euro(slot.cost_eur, lang)} Euro. "
            f"Reason: {slot.reason}."
            for slot in slots
        ]
        lines.append(f"Total cost: {_euro(total_cost_eur, lang)} Euro.")
        for gap in unscheduled:
            lines.append(f"Not schedulable: {gap}.")
        if facts:
            lines.append("Household facts:")
            lines.extend(f"- {fact}" for fact in facts)
        return "\n".join(lines)
    lines = [
        f"- {slot.device}: {slot.start} bis {slot.end}, "
        f"{_euro(slot.energy_kwh, lang)} kWh, "
        f"Durchschnitt {_euro(slot.price_ct_kwh, lang)} ct/kWh, "
        f"Grund: {slot.reason}. "
        f"Kosten {_euro(slot.cost_eur, lang)} Euro."
        for slot in slots
    ]
    lines.append(f"Gesamtkosten: {_euro(total_cost_eur, lang)} Euro.")
    for gap in unscheduled:
        lines.append(f"Nicht planbar: {gap}.")
    if facts:
        lines.append("Haushaltsangaben:")
        lines.extend(f"- {fact}" for fact in facts)
    return "\n".join(lines)


def build_citations(
    slots: list[ScheduledSlot],
    total_cost_eur: float,
    constraints: HouseholdConstraints,
    unscheduled: list[str],
    price_source: str,
    lang: str = "de",
) -> list[Citation]:
    """Cite every slot, the total, every window, and every gap."""
    lang = "en" if lang == "en" else "de"
    joiner = "to" if lang == "en" else "bis"
    citations = [
        Citation(
            claim=f"{slot.device} runs {slot.start} {joiner} {slot.end}"
            if lang == "en"
            else f"{slot.device} läuft {slot.start} bis {slot.end}",
            source="day-ahead",
            detail=(
                f"Ø {_euro(slot.price_ct_kwh, lang)} ct/kWh all-in ({price_source})"
            ),
        )
        for slot in slots
    ]
    citations.append(
        Citation(
            claim=f"Total cost {_euro(total_cost_eur, lang)} Euro"
            if lang == "en"
            else f"Gesamtkosten {_euro(total_cost_eur, lang)} Euro",
            source="tariff",
            detail="all-in incl. levies and VAT"
            if lang == "en"
            else "all-in inkl. Umlagen und MwSt",
        )
    )
    for device in constraints.devices:
        if device.shiftable:
            claim = (
                f"{device.device} flexible {device.earliest} {joiner} {device.latest}"
                if lang == "en"
                else f"{device.device} flexibel {device.earliest} bis {device.latest}"
            )
        else:
            claim = (
                f"{device.device} runs at a fixed time"
                if lang == "en"
                else f"{device.device} läuft zu fester Zeit"
            )
        citations.append(
            Citation(
                claim=claim,
                source="household",
                detail="time window from household input"
                if lang == "en"
                else "Zeitfenster aus Haushaltsangabe",
            )
        )
    for gap in unscheduled:
        citations.append(
            Citation(
                claim=gap,
                source="planner",
                detail="no matching window on the target day"
                if lang == "en"
                else "kein passendes Fenster im Zieltageszeitraum",
            )
        )
    return citations


def _to_minutes(hours: str, minutes: str) -> int:
    """Convert a regex time match to minutes since midnight."""
    return int(hours) * 60 + int(minutes)


def check_faithfulness(
    text: str,
    slots: list[ScheduledSlot],
    total_cost_eur: float,
    lang: str = "de",
    windows: Sequence[tuple[str, str]] = (),
) -> list[str]:
    """List every time, amount, or device the plan does not back."""
    violations: list[str] = []
    backed_minutes = {_to_minutes(*slot.start.split(":")) for slot in slots}
    backed_minutes |= {_to_minutes(*slot.end.split(":")) for slot in slots}
    for earliest, latest in windows:
        backed_minutes.add(_to_minutes(*earliest.split(":")))
        backed_minutes.add(_to_minutes(*latest.split(":")))
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
        name = slot.device.lower().translate(_FOLD)
        if name in folded:
            continue
        aliases = _DEVICE_ALIASES.get(name, []) if lang == "en" else []
        if any(re.search(rf"\b{re.escape(alias)}\b", folded) for alias in aliases):
            continue
        violations.append(f"Gerät {slot.device} fehlt im Text")
    return violations


def narrate(
    slots: list[ScheduledSlot],
    total_cost_eur: float,
    constraints: HouseholdConstraints,
    unscheduled: list[str],
    price_source: str,
    router: ChatRouter,
    facts: Sequence[str] = (),
    system_prompt: str | None = None,
    lang: str = "de",
) -> tuple[Narration, str]:
    """Draft the narration with one repair retry plus citations."""
    lang = "en" if lang == "en" else "de"
    brief = _brief(slots, total_cost_eur, unscheduled, lang, facts)
    windows = [(device.earliest, device.latest) for device in constraints.devices]
    messages = [
        Message(role="system", content=system_prompt or _SYSTEM[lang]),
        Message(role="user", content=_EXAMPLE_BULLETS[lang]),
        Message(role="assistant", content=_EXAMPLE_REPLY[lang]),
        Message(role="user", content=brief),
    ]
    result = router.chat("explainer", messages, NARRATE_TOKENS, LOW_EFFORT)
    violations = check_faithfulness(
        result.content, slots, total_cost_eur, lang, windows
    )
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
        violations = check_faithfulness(
            result.content, slots, total_cost_eur, lang, windows
        )
    citations = build_citations(
        slots, total_cost_eur, constraints, unscheduled, price_source, lang
    )
    return Narration(
        text=result.content, citations=citations, violations=violations
    ), result.model
