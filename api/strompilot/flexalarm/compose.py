"""Alert composer: deterministic titles and bodies, German or English."""

from .models import AlertCandidate, TriageVerdict

_KIND_TITLE = {
    "de": {
        "cheap_window": "Billigstrom",
        "price_spike": "Stromspitze",
        "negative_prices": "Negativpreise",
    },
    "en": {
        "cheap_window": "Cheap power",
        "price_spike": "Power spike",
        "negative_prices": "Negative prices",
    },
}

_FALLBACK_TITLE = {"de": "Stromalarm", "en": "Power alert"}


def _amount(value: float, lang: str) -> str:
    """Format ct/kWh with a decimal comma (de) or point (en)."""
    text = f"{value:.2f}"
    return text.replace(".", ",") if lang == "de" else text


def _hint(candidate: AlertCandidate, lang: str) -> str:
    """Explain why the window matters in the household language."""
    mean = _amount(candidate.mean_ct_kwh, lang)
    if candidate.kind == "negative_prices":
        extreme = _amount(candidate.extreme_ct_kwh, lang)
        if lang == "en":
            return (
                "Prices are negative: consuming now earns money back. "
                f"Lowest point {extreme} ct/kWh."
            )
        return (
            "Die Preise sind negativ: Wer jetzt verbraucht, bekommt Geld raus. "
            f"Tiefstwert {extreme} ct/kWh."
        )
    if candidate.kind == "price_spike":
        if lang == "en":
            return (
                "The spike sits well above the daily mean of "
                f"{mean} ct/kWh. Better shift big loads."
            )
        return (
            "Die Spitze liegt deutlich über dem Tagesmittel von "
            f"{mean} ct/kWh. "
            "Großverbraucher lieber verschieben."
        )
    if lang == "en":
        return (
            f"This is the cheapest window of the day at a daily mean of {mean} ct/kWh."
        )
    return (
        "Das ist das billigste Fenster des Tages bei einem Tagesmittel von "
        f"{mean} ct/kWh."
    )


def compose(
    candidate: AlertCandidate, verdict: TriageVerdict, lang: str = "de"
) -> tuple[str, str]:
    """Compose the alert title and body from candidate facts."""
    lang = "en" if lang == "en" else "de"
    label = _KIND_TITLE[lang].get(candidate.kind, _FALLBACK_TITLE[lang])
    avg = _amount(candidate.avg_ct_kwh, lang)
    if lang == "en":
        title = f"{label} {avg} ct/kWh, {candidate.start} to {candidate.end}"
        body = (
            f"From {candidate.start} to {candidate.end} power costs "
            f"{avg} ct/kWh on average. "
            f"{_hint(candidate, lang)} {verdict.reason.strip()}"
        )
        return title, body
    title = f"{label} {avg} ct/kWh, {candidate.start} bis {candidate.end} Uhr"
    body = (
        f"Von {candidate.start} bis {candidate.end} Uhr kostet Strom im Schnitt "
        f"{avg} ct/kWh. {_hint(candidate, lang)} {verdict.reason.strip()}"
    )
    return title, body
