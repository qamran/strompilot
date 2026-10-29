"""All-in price math: fixed lines plus VAT, rounded like a bill."""

from pydantic import BaseModel

from strompilot.tariff.defaults import TariffDefaults


class LineItem(BaseModel):
    """One priced line in ct/kWh, rounded for display."""

    name: str
    ct_per_kwh: float


class Decomposition(BaseModel):
    """Full all-in breakdown for one spot price."""

    lines: list[LineItem]
    subtotal_ex_vat: float
    vat_amount: float
    total: float


def decompose(spot_eur_per_mwh: float, defaults: TariffDefaults) -> Decomposition:
    """Decompose one spot price into all-in lines plus VAT."""
    raw = [
        ("spot", spot_eur_per_mwh / 10),
        ("procurement_addon", defaults.procurement_addon_ct_per_kwh.value),
        ("grid", defaults.grid_ct_per_kwh.value),
        ("kwkg", defaults.kwkg_ct_per_kwh.value),
        ("offshore", defaults.offshore_ct_per_kwh.value),
        ("stromnev", defaults.stromnev_ct_per_kwh.value),
        ("concession", defaults.concession_ct_per_kwh.value),
        ("electricity_tax", defaults.electricity_tax_ct_per_kwh.value),
    ]
    lines = [LineItem(name=name, ct_per_kwh=round(value, 2)) for name, value in raw]
    subtotal = round(sum(value for _, value in raw), 2)
    vat = round(subtotal * defaults.vat_rate.value, 2)
    total = round(subtotal + vat, 2)
    return Decomposition(
        lines=lines, subtotal_ex_vat=subtotal, vat_amount=vat, total=total
    )


def monthly_fixed(defaults: TariffDefaults) -> float:
    """Return the fixed monthly cost in EUR excluding VAT."""
    return round(
        defaults.supplier_fee_eur_per_month.value
        + defaults.grid_base_eur_per_year.value / 12
        + defaults.metering_eur_per_year.value / 12,
        2,
    )


def estimate_monthly_bill(
    kwh: float, blended_ct_per_kwh: float, defaults: TariffDefaults
) -> float:
    """Estimate one monthly bill in EUR.

    The blended rate is the incl-VAT all-in total, and the fixed parts
    carry VAT too, as on a real German bill.
    """
    energy = kwh * blended_ct_per_kwh / 100
    fixed = monthly_fixed(defaults) * (1 + defaults.vat_rate.value)
    return round(energy + fixed, 2)
