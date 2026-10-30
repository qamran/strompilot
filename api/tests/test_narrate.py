"""Tests for the cited narration pipeline."""

from strompilot.lifeplan.narrate import (
    build_citations,
    check_faithfulness,
    narrate,
)
from strompilot.lifeplan.schemas import (
    DeviceConstraint,
    HouseholdConstraints,
    ScheduledSlot,
)
from strompilot.llm.client import SPARK_OPEN_MODEL
from tests.fakes import FakeRouter, reply

SLOT = ScheduledSlot(
    device="Waschmaschine",
    start="02:00",
    end="04:00",
    energy_kwh=4.0,
    price_ct_kwh=15.0,
    cost_eur=0.60,
    reason="Günstigste Stunden",
)
CONSTRAINTS = HouseholdConstraints(
    devices=[
        DeviceConstraint(
            device="Waschmaschine",
            power_kw=2.0,
            duration_h=2.0,
            earliest="00:00",
            latest="23:00",
        )
    ]
)
CLEAN = (
    "Die Waschmaschine läuft von 02:00 bis 04:00 Uhr und kostet 0,60 €. "
    "Die Gesamtkosten betragen 0,60 €."
)


def test_narrate_returns_cited_text() -> None:
    router = FakeRouter({"explainer": [reply(CLEAN, SPARK_OPEN_MODEL)]})
    narration, model = narrate([SLOT], 0.60, CONSTRAINTS, [], "awattar-live", router)
    assert narration.text == CLEAN
    assert narration.violations == []
    assert model == SPARK_OPEN_MODEL
    assert router.efforts == ["low"]
    assert router.temps == [None]
    assert len(narration.citations) >= 3


def test_narrate_speaks_english_when_asked() -> None:
    clean = (
        "The Waschmaschine runs from 02:00 to 04:00 and costs 0.60 Euro. "
        "The total cost is 0.60 Euro."
    )
    router = FakeRouter({"explainer": [reply(clean, SPARK_OPEN_MODEL)]})
    narration, _ = narrate(
        [SLOT], 0.60, CONSTRAINTS, [], "awattar-live", router, lang="en"
    )
    assert narration.text == clean
    assert "Reply in English" in router.prompts[0]
    joined = " ".join(
        f"{citation.claim} {citation.detail}" for citation in narration.citations
    )
    assert "Total cost 0.60 Euro" in joined


def test_check_faithfulness_passes_clean_text() -> None:
    assert check_faithfulness(CLEAN, [SLOT], 0.60) == []


def test_check_faithfulness_flags_unknown_time() -> None:
    text = "Die Waschmaschine läuft von 09:00 bis 10:00 Uhr."
    violations = check_faithfulness(text, [SLOT], 0.60)
    assert any("09:00" in violation for violation in violations)


def test_check_faithfulness_flags_invented_cost() -> None:
    text = "Die Waschmaschine läuft von 02:00 bis 04:00 und kostet 5,00 €."
    violations = check_faithfulness(text, [SLOT], 0.60)
    assert any("5,00" in violation for violation in violations)


def test_check_faithfulness_flags_missing_device() -> None:
    text = "Alles läuft von 02:00 bis 04:00 und kostet 0,60 €."
    violations = check_faithfulness(text, [SLOT], 0.60)
    assert any("Waschmaschine" in violation for violation in violations)


def test_check_faithfulness_accepts_dot_decimals() -> None:
    text = "Die Waschmaschine läuft 02:00 bis 04:00 und kostet 0.60 Euro."
    assert check_faithfulness(text, [SLOT], 0.60) == []


def test_check_faithfulness_folds_umlauts() -> None:
    slot = ScheduledSlot(
        device="Geschirrspueler",
        start="02:00",
        end="04:00",
        energy_kwh=3.0,
        price_ct_kwh=15.0,
        cost_eur=0.45,
        reason="x",
    )
    text = "Der Geschirrspüler läuft von 02:00 bis 04:00 Uhr."
    assert check_faithfulness(text, [slot], 0.45) == []


def test_narrate_retries_once_on_violations() -> None:
    bad = "Die Waschmaschine läuft von 09:00 bis 10:00 Uhr."
    router = FakeRouter({"explainer": [reply(bad), reply(CLEAN)]})
    narration, _ = narrate([SLOT], 0.60, CONSTRAINTS, [], "awattar-live", router)
    assert narration.text == CLEAN
    assert narration.violations == []
    assert router.calls == ["explainer", "explainer"]


def test_narrate_returns_leftover_violations() -> None:
    bad = "Die Waschmaschine läuft von 09:00 bis 10:00 Uhr."
    router = FakeRouter({"explainer": [reply(bad), reply(bad)]})
    narration, _ = narrate([SLOT], 0.60, CONSTRAINTS, [], "awattar-live", router)
    assert narration.violations != []


def test_citations_cover_slots_total_windows_and_gaps() -> None:
    constraints = HouseholdConstraints(
        devices=[
            CONSTRAINTS.devices[0],
            DeviceConstraint(
                device="E-Auto",
                power_kw=11.0,
                duration_h=4.0,
                earliest="22:00",
                latest="06:00",
            ),
        ]
    )
    citations = build_citations(
        [SLOT], 0.60, constraints, ["E-Auto: kein Fenster"], "awattar-live"
    )
    joined = " ".join(f"{citation.claim} {citation.detail}" for citation in citations)
    assert "Waschmaschine" in joined
    assert "Gesamtkosten" in joined
    assert "22:00" in joined
    assert "kein Fenster" in joined
    assert any(citation.source == "day-ahead" for citation in citations)
    assert any(citation.source == "tariff" for citation in citations)
    assert any(citation.source == "household" for citation in citations)
