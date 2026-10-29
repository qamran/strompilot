"""Deterministic schedule optimizer: cheapest feasible windows.

One calendar day of hourly bars in, optimal slots out. Runs never span
midnight because next-day prices do not exist yet at plan time, so
overnight windows match evening or early-morning bars of the target day.
"""

import math
from dataclasses import dataclass

from .schemas import (
    DeviceConstraint,
    HouseholdConstraints,
    PriceBar,
    ScheduledSlot,
)


@dataclass(frozen=True)
class OptimizedPlan:
    """Optimizer output: priced slots, total, and what did not fit."""

    slots: list[ScheduledSlot]
    total_cost_eur: float
    unscheduled: list[str]


def _minutes(value: str) -> int:
    """Convert HH:MM to minutes since midnight."""
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def _bar_usable(bar: PriceBar, earliest: int, latest: int) -> bool:
    """Whether the bar's full hour sits inside the window."""
    start = bar.hour * 60
    end = start + 60
    if earliest <= latest:
        return earliest <= start and end <= latest
    return earliest <= start or end <= latest


def _best_start(
    hours_needed: int, device: DeviceConstraint, bars: list[PriceBar]
) -> int | None:
    """Find the cheapest feasible start position, earliest on ties."""
    earliest = _minutes(device.earliest)
    latest = _minutes(device.latest)
    best: int | None = None
    best_cost = math.inf
    for index in range(len(bars) - hours_needed + 1):
        run = bars[index : index + hours_needed]
        if not all(_bar_usable(bar, earliest, latest) for bar in run):
            continue
        cost = sum(bar.price_ct_kwh for bar in run)
        if cost < best_cost:
            best_cost = cost
            best = index
    return best


def _schedule_one(
    device: DeviceConstraint, bars: list[PriceBar]
) -> ScheduledSlot | None:
    """Schedule one device, or None when nothing fits."""
    hours_needed = math.ceil(device.duration_h)
    start = _best_start(hours_needed, device, bars)
    if start is None:
        return None
    run = bars[start : start + hours_needed]
    average = round(sum(bar.price_ct_kwh for bar in run) / hours_needed, 2)
    energy = round(device.power_kw * device.duration_h, 2)
    return ScheduledSlot(
        device=device.device,
        start=f"{run[0].hour:02d}:00",
        end=f"{(run[-1].hour + 1) % 24:02d}:00",
        energy_kwh=energy,
        price_ct_kwh=average,
        cost_eur=round(energy * average / 100, 2),
        reason=f"Günstigste Stunden im Fenster (Ø {average:.2f} ct/kWh)",
    )


def _bar_overlaps(bar: PriceBar, earliest: int, latest: int) -> bool:
    """Whether the bar's hour touches the fixed window at all."""
    start = bar.hour * 60
    end = start + 60
    if earliest <= latest:
        return start < latest and end > earliest
    return start >= earliest or end <= latest


def _schedule_fixed(
    device: DeviceConstraint, bars: list[PriceBar]
) -> ScheduledSlot | None:
    """Price one fixed-time device at its exact window, never moving it."""
    earliest = _minutes(device.earliest)
    latest = _minutes(device.latest)
    run = [bar for bar in bars if _bar_overlaps(bar, earliest, latest)]
    if not run:
        return None
    average = round(sum(bar.price_ct_kwh for bar in run) / len(run), 2)
    energy = round(device.power_kw * device.duration_h, 2)
    return ScheduledSlot(
        device=device.device,
        start=device.earliest,
        end=device.latest,
        energy_kwh=energy,
        price_ct_kwh=average,
        cost_eur=round(energy * average / 100, 2),
        reason=f"Feste Zeit (Ø {average:.2f} ct/kWh)",
    )


def optimize(constraints: HouseholdConstraints, bars: list[PriceBar]) -> OptimizedPlan:
    """Place every shiftable device into its cheapest feasible hours."""
    ordered = sorted(bars, key=lambda bar: bar.hour)
    slots: list[ScheduledSlot] = []
    unscheduled: list[str] = []
    for device in constraints.devices:
        if not device.shiftable:
            slot = _schedule_fixed(device, ordered)
            if slot is None:
                unscheduled.append(
                    f"{device.device}: keine Preise für feste Zeit "
                    f"{device.earliest} bis {device.latest}"
                )
            else:
                slots.append(slot)
            continue
        slot = _schedule_one(device, ordered)
        if slot is None:
            hours = math.ceil(device.duration_h)
            unscheduled.append(
                f"{device.device}: kein passendes {hours}-Stunden-Fenster "
                f"zwischen {device.earliest} und {device.latest}"
            )
        else:
            slots.append(slot)
    total = round(sum(slot.cost_eur for slot in slots), 2)
    return OptimizedPlan(slots=slots, total_cost_eur=total, unscheduled=unscheduled)
