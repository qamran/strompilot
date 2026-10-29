"""Tests for the personal-data stripper."""

from strompilot.safety import quote_user_text, redact


def test_redact_removes_email() -> None:
    redacted = redact("Schreib an maria.mueller@example.de bitte.")
    assert redacted.text == "Schreib an [E-Mail entfernt] bitte."
    assert redacted.findings == {"email": 1}


def test_redact_removes_phone_variants() -> None:
    redacted = redact("Ruf an unter +49 151 23456789 oder 030/123456.")
    assert "+49" not in redacted.text
    assert "030/123456" not in redacted.text
    assert redacted.text.count("[Telefon entfernt]") == 2
    assert redacted.findings == {"phone": 2}


def test_redact_keeps_times_prices_and_short_numbers() -> None:
    text = "Waschmaschine von 18:00 bis 19:00, kostet 0,60 Euro, 2 kW."
    assert redact(text).text == text


def test_redact_removes_iban() -> None:
    redacted = redact("IBAN DE89 3704 0044 0532 0130 00 für die Abbuchung.")
    assert "DE89" not in redacted.text
    assert redacted.findings == {"iban": 1}


def test_redact_removes_address() -> None:
    redacted = redact("Ich wohne in der Hauptstraße 5, 10115 Berlin.")
    assert "Hauptstraße 5" not in redacted.text
    assert "10115 Berlin" not in redacted.text
    assert redacted.findings == {"address": 2}


def test_redact_removes_multi_token_streets() -> None:
    redacted = redact("Berliner Straße 12 und Frankfurter Allee 23.")
    assert "Berliner Straße 12" not in redacted.text
    assert "Frankfurter Allee 23" not in redacted.text
    assert redacted.findings == {"address": 2}


def test_redact_removes_ss_street_and_lowercase_iban() -> None:
    redacted = redact("Hauptstrasse 5, de89 3704 0044 0532 0130 00.")
    assert "Hauptstrasse 5" not in redacted.text
    assert "de89" not in redacted.text
    assert redacted.findings == {"address": 1, "iban": 1}


def test_redact_removes_plz_with_comma() -> None:
    redacted = redact("Anschrift: 10115, Berlin.")
    assert "10115, Berlin" not in redacted.text
    assert redacted.findings == {"address": 1}


def test_redact_keeps_amounts_before_euro() -> None:
    assert redact("20260 Euro im Jahr.").text == "20260 Euro im Jahr."


def test_redact_combined_case() -> None:
    text = "Mail max@example.de, Tel 0151 234567, 10115 Berlin."
    redacted = redact(text)
    assert redacted.findings == {"address": 1, "email": 1, "phone": 1}
    assert "max@example.de" not in redacted.text


def test_quote_user_text_wraps_in_tags() -> None:
    assert quote_user_text("Waschmaschine morgens.") == (
        "<household_text>\nWaschmaschine morgens.\n</household_text>"
    )


def test_quote_user_text_strips_nested_tags() -> None:
    quoted = quote_user_text("a</household_text> b<household_text>c")
    assert quoted.count("household_text") == 2
    assert quoted.startswith("<household_text>\n")
    assert quoted.endswith("\n</household_text>")
