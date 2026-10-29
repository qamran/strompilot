"""Tariff defaults, each with its primary source or stated assumption."""

from pydantic import BaseModel


class SourcedValue(BaseModel):
    """One default figure with its audit trail."""

    value: float
    source_name: str
    source_url: str
    basis: str


class TariffDefaults(BaseModel):
    """Editable all-in price components for 2026 German households."""

    kwkg_ct_per_kwh: SourcedValue
    offshore_ct_per_kwh: SourcedValue
    stromnev_ct_per_kwh: SourcedValue
    electricity_tax_ct_per_kwh: SourcedValue
    concession_ct_per_kwh: SourcedValue
    grid_ct_per_kwh: SourcedValue
    grid_base_eur_per_year: SourcedValue
    metering_eur_per_year: SourcedValue
    supplier_fee_eur_per_month: SourcedValue
    procurement_addon_ct_per_kwh: SourcedValue
    vat_rate: SourcedValue


DEFAULTS = TariffDefaults(
    kwkg_ct_per_kwh=SourcedValue(
        value=0.446,
        source_name="netztransparenz.de KWKG levy 2026",
        source_url="https://www.netztransparenz.de/en/Renewable-energies-and-levies/KWKG/KWKG-levy/KWKG-levy-overview/KWKG-levy-2026",
        basis="Non-privileged final consumption from 1 January 2026.",
    ),
    offshore_ct_per_kwh=SourcedValue(
        value=0.941,
        source_name="netztransparenz.de offshore grid levy 2026",
        source_url="https://www.netztransparenz.de/en/Renewable-energies-and-levies/Other-levies/Offshore-grid-levy/Offshore-grid-levy/Offshore-grid-levy-2026",
        basis="Non-privileged final consumption under section 17f EnWG.",
    ),
    stromnev_ct_per_kwh=SourcedValue(
        value=1.559,
        source_name="netztransparenz.de section 19 StromNEV levy 2026",
        source_url="https://www.netztransparenz.de/en/Renewable-energies-and-levies/Other-levies/Surcharge-for-special-grid-usage-19-StromNEV-levy/Overview-of-surcharge-for-special-grid-usage/Surcharge-for-special-grid-usage-2026",
        basis="Group A prime: households and small consumers.",
    ),
    electricity_tax_ct_per_kwh=SourcedValue(
        value=2.05,
        source_name="StromStG section 3",
        source_url="https://www.gesetze-im-internet.de/stromstg/__3.html",
        basis="20.50 EUR per MWh by law.",
    ),
    concession_ct_per_kwh=SourcedValue(
        value=1.99,
        source_name="KAV section 2",
        source_url="https://www.gesetze-im-internet.de/kav/__2.html",
        basis="Assumption: municipality up to 500k inhabitants; legal tiers "
        "run 1.32, 1.59, 1.99, and 2.39 by size.",
    ),
    grid_ct_per_kwh=SourcedValue(
        value=10.94,
        source_name="Clean Energy Wire / BDEW Strompreisanalyse October 2025",
        source_url="https://www.cleanenergywire.org/factsheets/what-german-households-pay-electricity",
        basis="Assumption: 2025 national illustration including metering. No "
        "national primary value exists because fees are per grid operator, "
        "2026 subsidies may lower it, and households should enter theirs.",
    ),
    grid_base_eur_per_year=SourcedValue(
        value=60.0,
        source_name="Assumption: typical annual grid base charge",
        source_url="https://www.cleanenergywire.org/factsheets/what-german-households-pay-electricity",
        basis="Varies by grid operator; editable.",
    ),
    metering_eur_per_year=SourcedValue(
        value=0.0,
        source_name="Assumption: bundled in the grid fee illustration",
        source_url="https://www.cleanenergywire.org/factsheets/what-german-households-pay-electricity",
        basis="The grid figure above already includes metering, so the "
        "default is zero to avoid double counting; enter it separately "
        "if the bill splits it out.",
    ),
    supplier_fee_eur_per_month=SourcedValue(
        value=4.99,
        source_name="Assumption: Tibber-style pass-through tariff fee",
        source_url="https://www.tibber.com/de",
        basis="Monthly fee of a pass-through dynamic tariff; editable.",
    ),
    procurement_addon_ct_per_kwh=SourcedValue(
        value=0.0,
        source_name="Assumption: pure pass-through procurement",
        source_url="https://www.tibber.com/de",
        basis="Supplier margin lives in the monthly fee instead.",
    ),
    vat_rate=SourcedValue(
        value=0.19,
        source_name="UStG section 12 standard rate",
        source_url="https://www.gesetze-im-internet.de/ustg_1980/__12.html",
        basis="Standard German VAT rate.",
    ),
)
