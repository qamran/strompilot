"""Tests for the learning loop: feedback rules and window shifts."""

import json
from pathlib import Path

import pytest

from strompilot.learning.apply import apply_learned_windows
from strompilot.learning.models import Feedback, LearningError
from strompilot.learning.update import LEARNED_KEY, update_from_feedback
from strompilot.lifeplan.optimize import optimize
from strompilot.lifeplan.schemas import DeviceConstraint, HouseholdConstraints
from tests.fakes import make_device, price_bars


def test_too_early_shifts_earliest_later() -> None:
    updated = update_from_feedback(
        Feedback(device="Waschmaschine", verdict="too_early"), {}
    )
    assert updated == {"Waschmaschine": {"earliest_shift_h": 1, "latest_shift_h": 0}}
    assert LEARNED_KEY == "learned_windows"


def test_too_late_shifts_latest_earlier() -> None:
    updated = update_from_feedback(Feedback(device="E-Auto", verdict="too_late"), {})
    assert updated == {"E-Auto": {"earliest_shift_h": 0, "latest_shift_h": -1}}


def test_good_records_nothing() -> None:
    assert (
        update_from_feedback(Feedback(device="Waschmaschine", verdict="good"), {}) == {}
    )


def test_shifts_accumulate_with_caps() -> None:
    current = {"Waschmaschine": {"earliest_shift_h": 11, "latest_shift_h": 0}}
    updated = update_from_feedback(
        Feedback(device="Waschmaschine", verdict="too_early"), current
    )
    assert updated["Waschmaschine"]["earliest_shift_h"] == 12
    again = update_from_feedback(
        Feedback(device="Waschmaschine", verdict="too_early"), updated
    )
    assert again["Waschmaschine"]["earliest_shift_h"] == 12


def test_other_devices_untouched() -> None:
    current = {"E-Auto": {"earliest_shift_h": 2, "latest_shift_h": 0}}
    updated = update_from_feedback(
        Feedback(device="Waschmaschine", verdict="too_late"), current
    )
    assert updated["E-Auto"] == {"earliest_shift_h": 2, "latest_shift_h": 0}
    assert updated["Waschmaschine"]["latest_shift_h"] == -1


def test_blank_device_rejected() -> None:
    with pytest.raises(ValueError, match="device"):
        Feedback(device="  ", verdict="good")
    with pytest.raises(LearningError, match="device"):
        update_from_feedback(
            Feedback.model_construct(device="  ", verdict="good", note=""), {}
        )


def test_apply_shifts_matched_windows() -> None:
    constraints = HouseholdConstraints(devices=[make_device()])
    learned = {"Waschmaschine": {"earliest_shift_h": 2, "latest_shift_h": -1}}
    applied = apply_learned_windows(constraints, learned)
    (washer,) = applied.devices
    assert (washer.earliest, washer.latest) == ("02:00", "22:00")
    assert applied.notes == constraints.notes


def test_apply_matches_names_case_insensitively() -> None:
    constraints = HouseholdConstraints(devices=[make_device()])
    applied = apply_learned_windows(
        constraints, {"waschmaschine": {"earliest_shift_h": 1, "latest_shift_h": 0}}
    )
    assert applied.devices[0].earliest == "01:00"


def test_apply_ignores_malformed_entries() -> None:
    constraints = HouseholdConstraints(devices=[make_device()])
    applied = apply_learned_windows(
        constraints,
        {
            "Waschmaschine": {"earliest_shift_h": "soon", "latest_shift_h": None},
            "E-Auto": "later",
        },
    )
    (washer,) = applied.devices
    assert (washer.earliest, washer.latest) == ("00:00", "23:00")


def test_apply_clamps_to_the_day() -> None:
    constraints = HouseholdConstraints(devices=[make_device()])
    applied = apply_learned_windows(
        constraints, {"Waschmaschine": {"earliest_shift_h": 30, "latest_shift_h": 0}}
    )
    assert applied.devices[0].earliest == "23:00"


def test_apply_wraps_overnight_starts_past_midnight() -> None:
    car = make_device(
        name="E-Auto", power_kw=11.0, duration_h=4.0, earliest="22:00", latest="06:00"
    )
    constraints = HouseholdConstraints(devices=[car])
    applied = apply_learned_windows(
        constraints, {"E-Auto": {"earliest_shift_h": 4, "latest_shift_h": 0}}
    )
    assert (applied.devices[0].earliest, applied.devices[0].latest) == (
        "02:00",
        "06:00",
    )


def test_apply_skips_fixed_devices() -> None:
    fixed = make_device(earliest="19:00", latest="20:00", shiftable=False)
    constraints = HouseholdConstraints(devices=[fixed])
    applied = apply_learned_windows(
        constraints, {"Waschmaschine": {"earliest_shift_h": 5, "latest_shift_h": 0}}
    )
    assert (applied.devices[0].earliest, applied.devices[0].latest) == (
        "19:00",
        "20:00",
    )


def golden_constraints(name: str) -> HouseholdConstraints:
    """Load one golden household's expected devices as constraints."""
    root = Path(__file__).parent / "fixtures" / "golden_households.json"
    goldens = json.loads(root.read_text(encoding="utf-8"))
    expected = next(item for item in goldens if item["name"] == name)["expected"]
    return HouseholdConstraints(
        devices=[DeviceConstraint.model_validate(item) for item in expected["devices"]]
    )


def test_golden_baseline_stays_stable() -> None:
    constraints = golden_constraints("washer-morning")
    plan = optimize(constraints, price_bars())
    assert [(slot.device, slot.start, slot.end) for slot in plan.slots] == [
        ("Waschmaschine", "06:00", "08:00")
    ]
    assert plan.unscheduled == []


def test_simulated_feedback_shifts_golden_plan() -> None:
    constraints = golden_constraints("washer-morning")
    learned = update_from_feedback(
        Feedback(device="Waschmaschine", verdict="too_early"), {}
    )
    plan = optimize(apply_learned_windows(constraints, learned), price_bars())
    assert [(slot.start, slot.end) for slot in plan.slots] == [("07:00", "09:00")]
