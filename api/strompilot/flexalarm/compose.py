"""Alert composer: deterministic German text from judged windows."""

from .models import AlertCandidate, TriageVerdict

_KIND_TITLE = {
    "cheap_window": "Billigstrom",
    "price_spike": "Stromspitze",
    "negative_prices": "Negativpreise",
}


def _euro(value: float) -> str:
    """Format ct/kWh with a German decimal comma."""
    return f"{value:.2f}".replace(".", ",")


def compose(candidate: AlertCandidate, verdict: TriageVerdict) -> tuple[str, str]:
    """Compose the alert title and body from candidate facts."""
    label = _KIND_TITLE.get(candidate.kind, "Stromalarm")
    title = (
        f"{label} {_euro(candidate.avg_ct_kwh)} ct/kWh,"
        f" {candidate.start} bis {candidate.end} Uhr"
    )
    if candidate.kind == "negative_prices":
        hint = (
            "Die Preise sind negativ: Wer jetzt verbraucht, bekommt Geld raus. "
            f"Tiefstwert {_euro(candidate.extreme_ct_kwh)} ct/kWh."
        )
    elif candidate.kind == "price_spike":
        hint = (
            "Die Spitze liegt deutlich über dem Tagesmittel von "
            f"{_euro(candidate.mean_ct_kwh)} ct/kWh. "
            "Großverbraucher lieber verschieben."
        )
    else:
        hint = (
            f"Das ist das billigste Fenster des Tages bei einem Tagesmittel von "
            f"{_euro(candidate.mean_ct_kwh)} ct/kWh."
        )
    body = (
        f"Von {candidate.start} bis {candidate.end} Uhr kostet Strom im Schnitt "
        f"{_euro(candidate.avg_ct_kwh)} ct/kWh. {hint} {verdict.reason.strip()}"
    )
    return title, body
