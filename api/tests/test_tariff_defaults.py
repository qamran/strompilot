"""Tests for the tariff defaults and their source trail."""

from strompilot.tariff.defaults import DEFAULTS


def test_every_default_links_its_source() -> None:
    for name in (
        "kwkg_ct_per_kwh",
        "offshore_ct_per_kwh",
        "stromnev_ct_per_kwh",
        "electricity_tax_ct_per_kwh",
        "concession_ct_per_kwh",
        "grid_ct_per_kwh",
        "grid_base_eur_per_year",
        "metering_eur_per_year",
        "supplier_fee_eur_per_month",
        "procurement_addon_ct_per_kwh",
        "vat_rate",
    ):
        valued = getattr(DEFAULTS, name)
        assert valued.source_name, name
        assert valued.source_url.startswith("http"), name
        assert valued.basis, name


def test_verified_2026_figures() -> None:
    assert DEFAULTS.kwkg_ct_per_kwh.value == 0.446
    assert DEFAULTS.offshore_ct_per_kwh.value == 0.941
    assert DEFAULTS.stromnev_ct_per_kwh.value == 1.559
    assert DEFAULTS.electricity_tax_ct_per_kwh.value == 2.05
    assert DEFAULTS.vat_rate.value == 0.19
