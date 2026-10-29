"""Tests for the standard-profile labels."""

from strompilot.tariff.labels import DISCLOSURE, ESTIMATE_LABEL


def test_labels_exist_in_german_and_english() -> None:
    assert ESTIMATE_LABEL["de"]
    assert ESTIMATE_LABEL["en"]
    assert DISCLOSURE["de"]
    assert DISCLOSURE["en"]


def test_disclosure_names_quarter_hourly_settlement() -> None:
    assert "Viertelstunde" in DISCLOSURE["de"]
    assert "quarter-hour" in DISCLOSURE["en"]
