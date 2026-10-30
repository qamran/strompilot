"""Triage judge: Spark Open on Baseten decides fire or skip."""

from strompilot.llm.client import LOW_EFFORT
from strompilot.llm.types import ChatRouter, LlmError, Message

from .models import AlertCandidate, TriageVerdict

TRIAGE_TOKENS = 500

_SYSTEM = {
    "de": """You triage electricity price alerts for one German household.
Reply with exactly one JSON object and nothing else:
{"fire": true or false, "reason": "one short German sentence, no numbers"}.
Fire only when the window is unusually good or bad and the household
can still act on it. Stay silent on ordinary days and on repeats of
recent alerts.""",
    "en": """You triage electricity price alerts for one German household.
Reply with exactly one JSON object and nothing else:
{"fire": true or false, "reason": "one short English sentence, no numbers"}.
Fire only when the window is unusually good or bad and the household
can still act on it. Stay silent on ordinary days and on repeats of
recent alerts.""",
}

_EXAMPLE_USER = """Kind: cheap_window. Day: 2026-06-01. Window: 02:00-04:00.
Average: 8.50 ct/kWh. Daily mean: 25.00 ct/kWh. Extreme: 8.00 ct/kWh.
Devices: E-Auto. Recent alerts: none."""
_EXAMPLE_REPLY = {
    "de": '{"fire": true, "reason": "Nachtstrom kostet nur einen Bruchteil"}',
    "en": '{"fire": true, "reason": "Night power costs only a fraction"}',
}


def _brief(candidate: AlertCandidate, devices: list[str], recent: list[str]) -> str:
    """Render the candidate facts for the judge prompt."""
    device_text = ", ".join(devices) if devices else "none"
    recent_text = "; ".join(recent) if recent else "none"
    return (
        f"Kind: {candidate.kind}. Day: {candidate.day.isoformat()}. "
        f"Window: {candidate.start}-{candidate.end}. "
        f"Average: {candidate.avg_ct_kwh:.2f} ct/kWh. "
        f"Daily mean: {candidate.mean_ct_kwh:.2f} ct/kWh. "
        f"Extreme: {candidate.extreme_ct_kwh:.2f} ct/kWh. "
        f"Devices: {device_text}. Recent alerts: {recent_text}."
    )


def judge(
    candidate: AlertCandidate,
    devices: list[str],
    recent: list[str],
    router: ChatRouter,
    lang: str = "de",
) -> TriageVerdict:
    """Ask the watcher leg for a verdict, failing closed to skip."""
    lang = "en" if lang == "en" else "de"
    messages = [
        Message(role="system", content=_SYSTEM[lang]),
        Message(role="user", content=_EXAMPLE_USER),
        Message(role="assistant", content=_EXAMPLE_REPLY[lang]),
        Message(role="user", content=_brief(candidate, devices, recent)),
    ]
    try:
        result = router.chat("watcher", messages, TRIAGE_TOKENS, LOW_EFFORT, 0.0)
    except LlmError:
        return TriageVerdict(fire=False, reason="triage failed")
    try:
        verdict = TriageVerdict.model_validate_json(result.content)
    except ValueError:
        return TriageVerdict(fire=False, reason="triage reply unparseable")
    if not verdict.reason.strip():
        return TriageVerdict(fire=False, reason="triage reply unparseable")
    return verdict
