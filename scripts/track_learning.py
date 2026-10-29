"""Improvement tracker: baselines plus simulated feedback per golden.

Optimizes every golden household on the fixed reference curve, prints
the baseline slots beside the slots after simulated feedback, and
fails when any baseline drifts from the pinned fixture. Deterministic
and offline; run manually or from CI. Pass --write-baseline once to
regenerate the pinned fixture after reviewing the values.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, "api")

from strompilot.learning.apply import apply_learned_windows
from strompilot.learning.models import Feedback, Verdict
from strompilot.learning.update import update_from_feedback
from strompilot.lifeplan.optimize import optimize
from strompilot.lifeplan.schemas import DeviceConstraint, HouseholdConstraints
from tests.fakes import price_bars

FIXTURE = Path("api/tests/fixtures/learning_baseline.json")
GOLDENS = Path("api/tests/fixtures/golden_households.json")

# Simulated verdicts per golden: (device, verdict, repetitions).
SIMULATED: dict[str, list[tuple[str, Verdict, int]]] = {
    "washer-morning": [("Waschmaschine", "too_early", 1)],
    "ev-night-dishwasher-evening": [
        ("E-Auto", "too_early", 4),
        ("Geschirrspueler", "too_late", 1),
    ],
    "stove-fixed-time": [("Herd", "too_early", 1)],
    "washer-dryer-morning-typicals": [
        ("Waschmaschine", "too_early", 1),
        ("Trockner", "too_early", 2),
    ],
}


def constraints_for(devices: list[dict[str, object]]) -> HouseholdConstraints:
    """Build constraints from one golden's expected devices."""
    return HouseholdConstraints(
        devices=[DeviceConstraint.model_validate(item) for item in devices]
    )


def snapshot(plan: object) -> list[str]:
    """Render one plan as comparable slot lines."""
    from strompilot.lifeplan.optimize import OptimizedPlan

    assert isinstance(plan, OptimizedPlan)
    lines = [
        f"{slot.device} {slot.start}-{slot.end} {slot.cost_eur:.2f} EUR"
        for slot in plan.slots
    ]
    return [*lines, *[f"UNSCHEDULED {gap}" for gap in plan.unscheduled]]


def main() -> None:
    """Run the tracker, optionally rewriting the pinned baselines."""
    write = "--write-baseline" in sys.argv
    goldens = json.loads(GOLDENS.read_text(encoding="utf-8"))
    bars = price_bars()
    baselines: dict[str, list[str]] = {}
    drift = 0
    pinned = json.loads(FIXTURE.read_text(encoding="utf-8")) if FIXTURE.exists() else {}
    for golden in goldens:
        name = golden["name"]
        constraints = constraints_for(golden["expected"]["devices"])
        base = snapshot(optimize(constraints, bars))
        baselines[name] = base
        learned: dict[str, dict[str, int]] = {}
        for device, verdict, times in SIMULATED.get(name, []):
            for _ in range(times):
                learned = update_from_feedback(
                    Feedback(device=device, verdict=verdict), learned
                )
        shifted = snapshot(optimize(apply_learned_windows(constraints, learned), bars))
        print(f"== {name}")
        for line in base:
            print(f"  base: {line}")
        for line in shifted:
            print(f"  learned: {line}")
        if not write and pinned.get(name) != base:
            drift += 1
            print(f"  DRIFT: baseline differs from {FIXTURE}")
    if write:
        FIXTURE.write_text(json.dumps(baselines, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {FIXTURE}")
    elif drift:
        raise SystemExit(f"{drift} golden baselines drifted")


if __name__ == "__main__":
    main()
