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
    hours_needed: int,
    device: DeviceConstraint,
    bars: list[PriceBar],
    committed: list[float],
    cap_kw: float,
) -> tuple[int | None, bool]:
    """Find the cheapest feasible start, skipping connection overloads.

    Returns the start position plus whether every feasible window
    overloads the house connection anyway.
    """
    earliest = _minutes(device.earliest)
    latest = _minutes(device.latest)
    best: int | None = None
    best_cost = math.inf
    fallback: int | None = None
    fallback_cost = math.inf
    for index in range(len(bars) - hours_needed + 1):
        run = bars[index : index + hours_needed]
        if not all(_bar_usable(bar, earliest, latest) for bar in run):
            continue
        cost = sum(bar.price_ct_kwh for bar in run)
        if cost < fallback_cost:
            fallback_cost = cost
            fallback = index
        positions = range(index, index + hours_needed)
        if any(committed[pos] + device.power_kw > cap_kw for pos in positions):
            continue
        if cost < best_cost:
            best_cost = cost
            best = index
    if best is not None:
        return best, False
    return fallback, fallback is not None


def _schedule_one(
    device: DeviceConstraint,
    bars: list[PriceBar],
    lang: str,
    committed: list[float],
    cap_kw: float,
) -> ScheduledSlot | None:
    """Schedule one device, or None when nothing fits."""
    hours_needed = math.ceil(device.duration_h)
    start, overloaded = _best_start(hours_needed, device, bars, committed, cap_kw)
    if start is None:
        return None
    for pos in range(start, start + hours_needed):
        committed[pos] += device.power_kw
    run = bars[start : start + hours_needed]
    average = round(sum(bar.price_ct_kwh for bar in run) / hours_needed, 2)
    energy = round(device.power_kw * device.duration_h, 2)
    if lang == "en":
        reason = (
            f"Cheapest {hours_needed}h between {device.earliest} "
            f"and {device.latest} (Ø {average:.2f} ct/kWh)"
        )
    else:
        reason = (
            f"Günstigste {hours_needed}h zwischen {device.earliest} "
            f"und {device.latest} (Ø {average:.2f} ct/kWh)"
        )
    if overloaded:
        if lang == "en":
            reason += f"; shares the {cap_kw:g} kW house connection"
        else:
            reason += f"; teilt sich den {cap_kw:g}-kW-Hausanschluss"
    return ScheduledSlot(
        device=device.device,
        start=f"{run[0].hour:02d}:00",
        end=f"{(run[-1].hour + 1) % 24:02d}:00",
        energy_kwh=energy,
        price_ct_kwh=average,
        cost_eur=round(energy * average / 100, 2),
        reason=reason,
    )


def _bar_overlaps(bar: PriceBar, earliest: int, latest: int) -> bool:
    """Whether the bar's hour touches the fixed window at all."""
    start = bar.hour * 60
    end = start + 60
    if earliest <= latest:
        return start < latest and end > earliest
    return start >= earliest or end <= latest


def _schedule_fixed(
    device: DeviceConstraint, bars: list[PriceBar], lang: str
) -> ScheduledSlot | None:
    """Price one fixed-time device at its exact window, never moving it."""
    earliest = _minutes(device.earliest)
    latest = _minutes(device.latest)
    run = [bar for bar in bars if _bar_overlaps(bar, earliest, latest)]
    if not run:
        return None
    average = round(sum(bar.price_ct_kwh for bar in run) / len(run), 2)
    energy = round(device.power_kw * device.duration_h, 2)
    if lang == "en":
        reason = (
            f"Fixed time {device.earliest} to {device.latest} (Ø {average:.2f} ct/kWh)"
        )
    else:
        reason = (
            f"Feste Zeit {device.earliest} bis {device.latest} (Ø {average:.2f} ct/kWh)"
        )
    return ScheduledSlot(
        device=device.device,
        start=device.earliest,
        end=device.latest,
        energy_kwh=energy,
        price_ct_kwh=average,
        cost_eur=round(energy * average / 100, 2),
        reason=reason,
    )


def _bar_order(bar: PriceBar) -> tuple[str, int]:
    """Order bars by true UTC start, falling back to the nominal hour."""
    return (str(bar.start_utc), bar.hour)


def _commit_fixed(
    device: DeviceConstraint, bars: list[PriceBar], committed: list[float]
) -> None:
    """Reserve house-connection load for one immovable device."""
    earliest = _minutes(device.earliest)
    latest = _minutes(device.latest)
    for pos, bar in enumerate(bars):
        if _bar_overlaps(bar, earliest, latest):
            committed[pos] += device.power_kw


def optimize(
    constraints: HouseholdConstraints, bars: list[PriceBar], lang: str = "de"
) -> OptimizedPlan:
    """Place every shiftable device into its cheapest feasible hours."""
    lang = "en" if lang == "en" else "de"
    ordered = sorted(bars, key=_bar_order)
    committed = [0.0] * len(ordered)
    for device in constraints.devices:
        if not device.shiftable:
            _commit_fixed(device, ordered, committed)
    slots: list[ScheduledSlot] = []
    unscheduled: list[str] = []
    cap_kw = constraints.max_concurrent_kw
    for device in constraints.devices:
        if not device.shiftable:
            slot = _schedule_fixed(device, ordered, lang)
            if slot is None:
                if lang == "en":
                    unscheduled.append(
                        f"{device.device}: no prices for fixed time "
                        f"{device.earliest} to {device.latest}"
                    )
                else:
                    unscheduled.append(
                        f"{device.device}: keine Preise für feste Zeit "
                        f"{device.earliest} bis {device.latest}"
                    )
            else:
                slots.append(slot)
            continue
        slot = _schedule_one(device, ordered, lang, committed, cap_kw)
        if slot is None:
            hours = math.ceil(device.duration_h)
            if lang == "en":
                unscheduled.append(
                    f"{device.device}: no matching {hours}-hour window "
                    f"between {device.earliest} and {device.latest}"
                )
            else:
                unscheduled.append(
                    f"{device.device}: kein passendes {hours}-Stunden-Fenster "
                    f"zwischen {device.earliest} und {device.latest}"
                )
        else:
            slots.append(slot)
    total = round(sum(slot.cost_eur for slot in slots), 2)
    return OptimizedPlan(slots=slots, total_cost_eur=total, unscheduled=unscheduled)
