"""Household safety: personal-data stripping plus prompt quoting."""

import re
from collections.abc import Callable
from dataclasses import dataclass, field

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE_RE = re.compile(r"\+49[\d\s/\-.()]{6,}|0\d[\d\s/\-.()]{6,}")
_IBAN_RE = re.compile(r"\bDE\d{2}(?:\s?\d{4}){4}\s?\d{2}\b", re.IGNORECASE)
_PLZ_RE = re.compile(
    r"\b\d{5},?\s+[A-Za-zÄÖÜäöüß]+(?:-[A-Za-zÄÖÜäöüß]+)?\b",
    re.IGNORECASE,
)
_STREET_RE = re.compile(
    r"\b(?:"
    r"[A-ZÄÖÜ][a-zäöüß]+(?:straße|strasse|weg|allee|platz)\s+\d+[a-z]?"
    r"|[A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)*\s+"
    r"(?:Straße|Strasse|Str\.|Weg|Allee|Platz)\s+\d+[a-z]?"
    r")\b"
)
_TAG_RE = re.compile(r"</?household_text>")
# Lowercase words that follow 5-digit numbers but are never cities.
# Recall beats precision here: over-redacting a false city costs
# nothing for planning, while a leaked address costs privacy.
_CITY_STOPLIST = frozenset(
    {
        "euro",
        "cent",
        "kwh",
        "watt",
        "wattstunden",
        "strom",
        "kosten",
        "plan",
        "tag",
        "monat",
        "jahr",
        "uhr",
    }
)


@dataclass(frozen=True)
class Redaction:
    """Stripped text plus what was removed, by kind."""

    text: str
    findings: dict[str, int] = field(default_factory=dict)


def _is_phone(match: str) -> bool:
    """Accept phone candidates with at least 8 digits."""
    return sum(char.isdigit() for char in match) >= 8


def _is_city(match: str) -> bool:
    """Reject PLZ matches whose city word is a unit or noun."""
    city = match.split(None, 1)[1].split("-")[0].rstrip(",").lower()
    return city not in _CITY_STOPLIST


def redact(text: str) -> Redaction:
    """Strip emails, phones, IBANs, and addresses from one text."""
    findings: dict[str, int] = {}

    def scrub(
        pattern: re.Pattern[str],
        label: str,
        kind: str,
        current: str,
        accept: Callable[[str], bool] | None = None,
    ) -> str:
        def replace(match: re.Match[str]) -> str:
            if accept is not None and not accept(match.group(0)):
                return match.group(0)
            findings[kind] = findings.get(kind, 0) + 1
            return label

        return pattern.sub(replace, current)

    scrubbed = scrub(_EMAIL_RE, "[E-Mail entfernt]", "email", text)
    scrubbed = scrub(_IBAN_RE, "[IBAN entfernt]", "iban", scrubbed)
    scrubbed = scrub(_PHONE_RE, "[Telefon entfernt]", "phone", scrubbed, _is_phone)
    scrubbed = scrub(_PLZ_RE, "[Adresse entfernt]", "address", scrubbed, _is_city)
    scrubbed = scrub(_STREET_RE, "[Adresse entfernt]", "address", scrubbed)
    return Redaction(text=scrubbed, findings=findings)


def quote_user_text(text: str) -> str:
    """Wrap household text in tags that mark it as data, not orders."""
    clean = _TAG_RE.sub("", text)
    return f"<household_text>\n{clean}\n</household_text>"
