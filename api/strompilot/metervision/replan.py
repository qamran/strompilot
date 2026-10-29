"""Re-plan math: device costs plus calibrated background use."""

from datetime import date

from strompilot.lifeplan.optimize import optimize
from strompilot.lifeplan.schemas import (
    DeviceConstraint,
    HouseholdConstraints,
    PriceBar,
)
from strompilot.prices.models import BERLIN
from strompilot.tariff.profiles import HourlyBaseline, baseline_day

from .models import PlanTotals, ReplanDiff


def plan_totals(
    devices: list[DeviceConstraint],
    bars: list[PriceBar],
    baseline: list[HourlyBaseline],
    day: date,
    annual_kwh: float = 0.0,
) -> PlanTotals:
    """Price one day: optimized devices plus background use at bar rates."""
    plan = optimize(HouseholdConstraints(devices=devices), bars)
    by_hour = {bar.hour: bar.price_ct_kwh for bar in bars}
    background_kwh = 0.0
    background_cost = 0.0
    for hour in baseline:
        rate = by_hour.get(hour.start.astimezone(BERLIN).hour)
        if rate is None:
            continue
        background_kwh += hour.kwh
        background_cost += hour.kwh * rate / 100
    background_kwh = round(background_kwh, 2)
    background_cost = round(background_cost, 2)
    return PlanTotals(
        day=day.isoformat(),
        annual_kwh=annual_kwh,
        device_cost_eur=plan.total_cost_eur,
        baseline_kwh=background_kwh,
        baseline_cost_eur=background_cost,
        total_eur=round(plan.total_cost_eur + background_cost, 2),
        slots=len(plan.slots),
    )


def day_plan_totals(
    devices: list[DeviceConstraint],
    bars: list[PriceBar],
    annual_kwh: float,
    day: date,
) -> PlanTotals:
    """Price one day against the H25 baseline for the annual use."""
    return plan_totals(devices, bars, baseline_day(day, annual_kwh), day, annual_kwh)


def diff_totals(before: PlanTotals, after: PlanTotals) -> ReplanDiff:
    """Diff two totals; devices never move on a calibration change."""
    same = (
        before.device_cost_eur == after.device_cost_eur and before.slots == after.slots
    )
    delta = after.total_eur - before.total_eur
    direction = "steigen" if delta >= 0 else "sinken"
    note = (
        f"Hintergrund {before.baseline_kwh:.2f} auf "
        f"{after.baseline_kwh:.2f} kWh, Tageskosten {direction} um "
        f"{abs(delta):.2f} Euro."
    )
    return ReplanDiff(before=before, after=after, devices_unchanged=same, note=note)
