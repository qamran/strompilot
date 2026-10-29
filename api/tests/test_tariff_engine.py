"""Tests for the all-in price math with known answers."""

from strompilot.tariff.defaults import DEFAULTS
from strompilot.tariff.engine import (
    decompose,
    estimate_monthly_bill,
    monthly_fixed,
)


def test_known_answer_decomposition() -> None:
    result = decompose(100.0, DEFAULTS)
    lines = {line.name: line.ct_per_kwh for line in result.lines}
    assert lines["spot"] == 10.0
    assert lines["grid"] == 10.94
    assert lines["kwkg"] == 0.45
    assert lines["offshore"] == 0.94
    assert lines["stromnev"] == 1.56
    assert lines["concession"] == 1.99
    assert lines["electricity_tax"] == 2.05
    assert result.subtotal_ex_vat == 27.93
    assert result.vat_amount == 5.31
    assert result.total == 33.24


def test_decomposition_sums_within_rounding() -> None:
    result = decompose(258.28, DEFAULTS)
    shown = sum(line.ct_per_kwh for line in result.lines)
    assert abs(shown - result.subtotal_ex_vat) <= 0.05
    assert round(result.subtotal_ex_vat + result.vat_amount, 2) == result.total


def test_monthly_fixed_and_bill_estimate() -> None:
    assert monthly_fixed(DEFAULTS) == 9.99
    assert estimate_monthly_bill(300.0, 33.24, DEFAULTS) == 111.61
