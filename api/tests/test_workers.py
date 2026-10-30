"""Tests for the worker nodes with a scripted router."""

import pytest

from strompilot.agents.state import PlanState, Slot
from strompilot.agents.workers import (
    analyst_node,
    critic_node,
    explainer_node,
    perceive_node,
    publish_node,
    scheduler_node,
)
from strompilot.lifeplan.errors import LifeplanError
from strompilot.lifeplan.schemas import HouseholdConstraints
from strompilot.llm.client import SPARK_MODEL, SPARK_OPEN_MODEL
from strompilot.llm.types import LlmError
from tests.fakes import (
    ANALYST_JSON,
    FakeRouter,
    make_device,
    reply,
    stub_loader,
)


def test_perceive_marks_planning_intent() -> None:
    router = FakeRouter({"supervisor": [reply("plan")]})
    update = perceive_node(PlanState(request="plane meinen Tag"), router)
    assert update["intent"] == "plan"
    assert update["attribution"] == {"intent": SPARK_MODEL}
    assert any("perceive" in event for event in update["audit"])


def test_perceive_marks_other_intent() -> None:
    router = FakeRouter({"supervisor": [reply("other")]})
    update = perceive_node(PlanState(request="erzaehl einen Witz"), router)
    assert update["intent"] == "other"


def test_perceive_quotes_request() -> None:
    router = FakeRouter({"supervisor": [reply("plan")]})
    perceive_node(PlanState(request="plane"), router)
    (prompt,) = router.prompts
    assert "<household_text>" in prompt


def test_perceive_budgets_enough_tokens_to_answer() -> None:
    """100 tokens starved the model into null content on real runs."""
    router = FakeRouter({"supervisor": [reply("plan")]})
    perceive_node(PlanState(request="plane"), router)
    assert router.budgets[0] >= 1000


def test_perceive_pins_temperature_for_reliability() -> None:
    """Classification is deterministic work, like extraction."""
    router = FakeRouter({"supervisor": [reply("plan")]})
    perceive_node(PlanState(request="plane"), router)
    assert router.temps == [0.0]


def test_perceive_prompt_shows_planning_examples() -> None:
    """The canonical night-shift text must read as planning, not other."""
    router = FakeRouter({"supervisor": [reply("plan")]})
    perceive_node(PlanState(request="plane"), router)
    (prompt,) = router.prompts
    assert "Nachtschicht" in prompt
    assert "Witz" in prompt


def test_analyst_extracts_facts_and_constraints() -> None:
    router = FakeRouter({"analyst": [reply(ANALYST_JSON)]})
    update = analyst_node(PlanState(request="plane"), router)
    assert update["analysis"] == ["billig nachts"]
    devices = update["constraints"]["devices"]
    assert [device["device"] for device in devices] == ["Waschmaschine"]
    assert update["attribution"] == {
        "analysis": SPARK_MODEL,
        "constraints": SPARK_MODEL,
    }


def test_analyst_error_propagates() -> None:
    router = FakeRouter({"analyst": [reply("nein"), reply("nein")]})
    with pytest.raises(LlmError, match="extraction failed"):
        analyst_node(PlanState(request="plane"), router)


def test_scheduler_optimizes_deterministically() -> None:
    constraints = HouseholdConstraints(devices=[make_device()]).model_dump()
    update = scheduler_node(
        PlanState(request="plane", constraints=constraints), stub_loader
    )
    (slot,) = update["schedule"]
    assert (slot["start"], slot["end"]) == ("02:00", "04:00")
    assert slot["cost_eur"] == 0.60
    assert update["total_cost_eur"] == 0.60
    assert update["unscheduled"] == []
    assert update["price_source"] == "test"
    assert len(update["prices"]) == 24
    assert update["attribution"] == {"schedule": "deterministic"}


def test_scheduler_reasons_follow_state_language() -> None:
    constraints = HouseholdConstraints(devices=[make_device()]).model_dump()
    update = scheduler_node(
        PlanState(request="plane", constraints=constraints, lang="en"), stub_loader
    )
    (slot,) = update["schedule"]
    assert slot["reason"] == "Cheapest hours in the window (Ø 15.00 ct/kWh)"


def test_explainer_narrates_in_state_language() -> None:
    router = FakeRouter({"explainer": [reply("Wash at night.", SPARK_OPEN_MODEL)]})
    update = explainer_node(PlanState(request="plane", lang="en"), router)
    assert "Reply in English" in router.prompts[0]
    joined = " ".join(
        f"{citation['claim']} {citation['detail']}" for citation in update["citations"]
    )
    assert "Total cost" in joined


def test_scheduler_rejects_missing_constraints() -> None:
    with pytest.raises(LifeplanError, match="constraints"):
        scheduler_node(PlanState(request="plane"), stub_loader)


def test_scheduler_marks_unfittable_devices() -> None:
    device = make_device(duration_h=5.0, earliest="18:00", latest="20:00")
    constraints = HouseholdConstraints(devices=[device]).model_dump()
    update = scheduler_node(
        PlanState(request="plane", constraints=constraints), stub_loader
    )
    assert update["schedule"] == []
    assert len(update["unscheduled"]) == 1
    assert "Waschmaschine" in update["unscheduled"][0]


def test_explainer_writes_narration() -> None:
    router = FakeRouter({"explainer": [reply("Wasche nachts.", SPARK_OPEN_MODEL)]})
    update = explainer_node(PlanState(request="plane"), router)
    assert update["narration"] == "Wasche nachts."
    assert update["attribution"] == {"narration": SPARK_OPEN_MODEL}
    assert update["violations"] == []
    assert len(update["citations"]) >= 1


def test_explainer_rejects_unpriced_slots() -> None:
    router = FakeRouter({"explainer": [reply("text")]})
    state = PlanState(
        request="plane",
        schedule=[
            Slot(
                device="Waschmaschine",
                start="02:00",
                end="04:00",
                reason="billig",
            )
        ],
    )
    with pytest.raises(LifeplanError, match="priced"):
        explainer_node(state, router)


def test_critic_approves_and_counts() -> None:
    router = FakeRouter({"critic": [reply('{"approved": true, "notes": []}')]})
    update = critic_node(PlanState(request="plane"), router)
    assert update["verdict"] == {"approved": True, "notes": []}
    assert update["iterations"] == 1
    assert "error" not in update


def test_critic_veto_loops_under_cap() -> None:
    router = FakeRouter(
        {"critic": [reply('{"approved": false, "notes": ["beleg fehlt"]}')]},
    )
    update = critic_node(PlanState(request="plane", iterations=1), router)
    assert update["verdict"] == {"approved": False, "notes": ["beleg fehlt"]}
    assert update["iterations"] == 2
    assert "error" not in update


def test_critic_veto_at_cap_sets_error() -> None:
    router = FakeRouter(
        {"critic": [reply('{"approved": false, "notes": ["beleg fehlt"]}')]},
    )
    update = critic_node(PlanState(request="plane", iterations=2), router)
    assert update["iterations"] == 3
    assert update["error"] == "review cap reached"


def test_critic_rejects_invalid_json() -> None:
    router = FakeRouter({"critic": [reply("vielleicht")]})
    with pytest.raises(LlmError, match="invalid"):
        critic_node(PlanState(request="plane"), router)


def test_workers_pin_reasoning_effort() -> None:
    router = FakeRouter(
        {
            "supervisor": [reply("plan")],
            "analyst": [reply(ANALYST_JSON)],
            "explainer": [reply("text")],
            "critic": [reply('{"approved": true, "notes": []}')],
        }
    )
    state = PlanState(request="plane")
    perceive_node(state, router)
    analyst_node(state, router)
    constraints = HouseholdConstraints(devices=[make_device()]).model_dump()
    scheduler_node(PlanState(request="plane", constraints=constraints), stub_loader)
    explainer_node(state, router)
    critic_node(state, router)
    assert router.calls == ["supervisor", "analyst", "explainer", "critic"]
    assert router.efforts == ["minimal", "low", "low", "low"]


def test_explainer_sees_schedule() -> None:
    text = "Die Waschmaschine läuft von 02:00 bis 04:00 Uhr."
    router = FakeRouter({"explainer": [reply(text)]})
    state = PlanState(
        request="plane",
        schedule=[
            Slot(
                device="Waschmaschine",
                start="02:00",
                end="04:00",
                reason="billig",
                energy_kwh=4.0,
                price_ct_kwh=15.0,
                cost_eur=0.60,
            )
        ],
    )
    explainer_node(state, router)
    (prompt,) = router.prompts
    assert "Waschmaschine" in prompt
    assert "02:00" in prompt


def test_critic_sees_schedule_and_narration() -> None:
    router = FakeRouter({"critic": [reply('{"approved": true, "notes": []}')]})
    state = PlanState(
        request="plane",
        schedule=[
            Slot(
                device="Waschmaschine",
                start="02:00",
                end="04:00",
                reason="billig",
            )
        ],
        narration="Wasche nachts.",
    )
    critic_node(state, router)
    (prompt,) = router.prompts
    assert "Waschmaschine" in prompt
    assert "Wasche nachts." in prompt
    assert "<household_text>" in prompt


def test_critic_treats_schedule_as_final() -> None:
    router = FakeRouter({"critic": [reply('{"approved": true, "notes": []}')]})
    critic_node(PlanState(request="plane", narration="text"), router)
    (prompt,) = router.prompts
    assert "final" in prompt


def test_critic_sees_violations_and_gaps() -> None:
    router = FakeRouter({"critic": [reply('{"approved": true, "notes": []}')]})
    state = PlanState(
        request="plane",
        narration="text",
        violations=["Uhrzeit 09:00 ohne Planbeleg"],
        unscheduled=["E-Auto: kein Fenster"],
    )
    critic_node(state, router)
    (prompt,) = router.prompts
    assert "09:00" in prompt
    assert "kein Fenster" in prompt


def test_publish_needs_approval() -> None:
    blocked = publish_node(PlanState(request="plane", approval="pending"))
    assert blocked.get("published", False) is False
    assert blocked["error"] == "publish blocked: approval pending"


def test_publish_marks_published_when_approved() -> None:
    update = publish_node(PlanState(request="plane", approval="approved"))
    assert update["published"] is True
    assert "error" not in update
