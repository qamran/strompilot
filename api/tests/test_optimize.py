"""Tests for the deterministic schedule optimizer."""

from strompilot.lifeplan.optimize import optimize
from strompilot.lifeplan.schemas import HouseholdConstraints
from tests.fakes import make_device as device
from tests.fakes import price_bars as make_bars


def test_picks_cheapest_feasible_window() -> None:
    plan = optimize(HouseholdConstraints(devices=[device()]), make_bars())
    assert len(plan.slots) == 1
    (slot,) = plan.slots
    assert slot.device == "Waschmaschine"
    assert (slot.start, slot.end) == ("02:00", "04:00")
    assert slot.energy_kwh == 4.0
    assert slot.price_ct_kwh == 15.0
    assert slot.cost_eur == 0.60
    assert "nstigste" in slot.reason
    assert plan.unscheduled == []
    assert plan.total_cost_eur == 0.60


def test_reasons_speak_english_when_asked() -> None:
    plan = optimize(HouseholdConstraints(devices=[device()]), make_bars(), lang="en")
    (slot,) = plan.slots
    assert slot.reason == "Cheapest 2h between 00:00 and 23:00 (Ø 15.00 ct/kWh)"
    stuck = optimize(
        HouseholdConstraints(
            devices=[device(duration_h=5.0, earliest="18:00", latest="20:00")]
        ),
        make_bars(),
        lang="en",
    )
    assert stuck.unscheduled == [
        "Waschmaschine: no matching 5-hour window between 18:00 and 20:00"
    ]


def test_reason_names_binding_window() -> None:
    plan = optimize(
        HouseholdConstraints(devices=[device(earliest="18:00", latest="20:00")]),
        make_bars(),
        lang="en",
    )
    (slot,) = plan.slots
    assert slot.reason == "Cheapest 2h between 18:00 and 20:00 (Ø 45.00 ct/kWh)"


def test_respects_narrow_window_despite_cheap_night() -> None:
    plan = optimize(
        HouseholdConstraints(devices=[device(earliest="18:00", latest="20:00")]),
        make_bars(),
    )
    (slot,) = plan.slots
    assert (slot.start, slot.end) == ("18:00", "20:00")
    assert slot.cost_eur == 1.80


def test_overnight_window_matches_early_morning_bars() -> None:
    plan = optimize(
        HouseholdConstraints(
            devices=[
                device(
                    name="E-Auto",
                    power_kw=11.0,
                    duration_h=4.0,
                    earliest="22:00",
                    latest="06:00",
                )
            ]
        ),
        make_bars(),
    )
    (slot,) = plan.slots
    assert (slot.start, slot.end) == ("00:00", "04:00")
    assert slot.energy_kwh == 44.0


def test_window_shorter_than_duration_stays_unscheduled() -> None:
    plan = optimize(
        HouseholdConstraints(
            devices=[device(duration_h=5.0, earliest="18:00", latest="20:00")]
        ),
        make_bars(),
    )
    assert plan.slots == []
    assert len(plan.unscheduled) == 1
    assert "Waschmaschine" in plan.unscheduled[0]
    assert plan.total_cost_eur == 0.0


def test_fixed_devices_get_priced_slots() -> None:
    stove = device(
        name="Herd",
        power_kw=2.0,
        duration_h=1.0,
        earliest="18:00",
        latest="19:00",
        shiftable=False,
    )
    plan = optimize(HouseholdConstraints(devices=[stove]), make_bars())
    (slot,) = plan.slots
    assert (slot.start, slot.end) == ("18:00", "19:00")
    assert slot.energy_kwh == 2.0
    assert slot.price_ct_kwh == 45.0
    assert slot.cost_eur == 0.90
    assert "Fest" in slot.reason
    assert plan.unscheduled == []
    assert plan.total_cost_eur == 0.90


def test_fractional_duration_places_whole_hours_bills_actual() -> None:
    plan = optimize(
        HouseholdConstraints(devices=[device(duration_h=1.5)]),
        make_bars(),
    )
    (slot,) = plan.slots
    assert (slot.start, slot.end) == ("02:00", "04:00")
    assert slot.energy_kwh == 3.0
    assert slot.cost_eur == 0.45


def test_total_sums_two_devices() -> None:
    plan = optimize(
        HouseholdConstraints(
            devices=[
                device(),
                device(
                    name="Geschirrspueler",
                    power_kw=1.5,
                    duration_h=1.0,
                    earliest="12:00",
                    latest="14:00",
                ),
            ]
        ),
        make_bars(),
    )
    assert len(plan.slots) == 2
    assert plan.total_cost_eur == round(0.60 + 1.5 * 18.0 / 100, 2)


def test_empty_prices_leave_everything_unscheduled() -> None:
    plan = optimize(HouseholdConstraints(devices=[device()]), [])
    assert plan.slots == []
    assert len(plan.unscheduled) == 1


def test_concurrent_cap_moves_third_device_out_of_cheapest_window() -> None:
    plan = optimize(
        HouseholdConstraints(
            devices=[
                device(name="E-Auto", power_kw=11.0, duration_h=2.0),
                device(),
                device(
                    name="Geschirrspueler",
                    power_kw=1.5,
                    duration_h=1.0,
                ),
            ]
        ),
        make_bars(),
        lang="en",
    )
    assert len(plan.slots) == 3
    by_device = {slot.device: slot for slot in plan.slots}
    assert (by_device["E-Auto"].start, by_device["E-Auto"].end) == ("02:00", "04:00")
    assert (by_device["Waschmaschine"].start, by_device["Waschmaschine"].end) == (
        "02:00",
        "04:00",
    )
    assert (by_device["Geschirrspueler"].start, by_device["Geschirrspueler"].end) == (
        "12:00",
        "13:00",
    )


def test_unavoidable_overload_notes_shared_connection() -> None:
    plan = optimize(
        HouseholdConstraints(
            devices=[device(name="E-Auto", power_kw=11.0, duration_h=2.0)],
            max_concurrent_kw=5.0,
        ),
        make_bars(),
        lang="en",
    )
    (slot,) = plan.slots
    assert (slot.start, slot.end) == ("02:00", "04:00")
    assert "connection" in slot.reason
    german = optimize(
        HouseholdConstraints(
            devices=[device(name="E-Auto", power_kw=11.0, duration_h=2.0)],
            max_concurrent_kw=5.0,
        ),
        make_bars(),
    )
    assert "Hausanschluss" in german.slots[0].reason


def test_scheduler_orders_dst_duplicates_by_true_time() -> None:
    from strompilot.lifeplan.schemas import PriceBar

    bars = [
        PriceBar(
            hour=2,
            price_ct_kwh=50.0,
            source="test",
            start_utc="2026-10-25T01:00:00+00:00",
        ),
        PriceBar(
            hour=2,
            price_ct_kwh=10.0,
            source="test",
            start_utc="2026-10-25T00:00:00+00:00",
        ),
        PriceBar(
            hour=3,
            price_ct_kwh=10.0,
            source="test",
            start_utc="2026-10-25T02:00:00+00:00",
        ),
    ]
    plan = optimize(
        HouseholdConstraints(
            devices=[device(duration_h=2.0, earliest="02:00", latest="04:00")]
        ),
        bars,
        lang="en",
    )
    (slot,) = plan.slots
    assert slot.price_ct_kwh == 30.0
