"""Tests for the worker nodes with a scripted router."""

import pytest

from strompilot.agents.state import CriticVerdict, PlanState, Slot
from strompilot.agents.workers import (
    analyst_node,
    critic_node,
    explainer_node,
    perceive_node,
    publish_node,
    scheduler_node,
)
from strompilot.llm.client import SPARK_MODEL, SPARK_OPEN_MODEL
from strompilot.llm.types import LlmError
from tests.fakes import FakeRouter, reply


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


def test_analyst_collects_facts() -> None:
    router = FakeRouter({"analyst": [reply("billig nachts\n\nteuer abends\n")]})
    update = analyst_node(PlanState(request="plane"), router)
    assert update["analysis"] == ["billig nachts", "teuer abends"]
    assert update["attribution"] == {"analysis": SPARK_MODEL}


def test_scheduler_parses_slots() -> None:
    body = (
        '[{"device": "Waschmaschine", "start": "02:00", '
        '"end": "04:00", "reason": "billig"}]'
    )
    router = FakeRouter({"scheduler": [reply(body)]})
    update = scheduler_node(PlanState(request="plane"), router)
    assert update["schedule"] == [
        {
            "device": "Waschmaschine",
            "start": "02:00",
            "end": "04:00",
            "reason": "billig",
        }
    ]


def test_scheduler_rejects_invalid_json() -> None:
    router = FakeRouter({"scheduler": [reply("kein json")]})
    with pytest.raises(LlmError, match="invalid"):
        scheduler_node(PlanState(request="plane"), router)


def test_scheduler_rejects_bad_slots() -> None:
    router = FakeRouter({"scheduler": [reply('[{"device": "x"}]')]})
    with pytest.raises(LlmError, match="invalid"):
        scheduler_node(PlanState(request="plane"), router)


def test_explainer_writes_narration() -> None:
    router = FakeRouter({"explainer": [reply("Wasche nachts.", SPARK_OPEN_MODEL)]})
    update = explainer_node(PlanState(request="plane"), router)
    assert update["narration"] == "Wasche nachts."
    assert update["attribution"] == {"narration": SPARK_OPEN_MODEL}


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
            "analyst": [reply("facts")],
            "scheduler": [reply("[]")],
            "explainer": [reply("text")],
            "critic": [reply('{"approved": true, "notes": []}')],
        }
    )
    state = PlanState(request="plane")
    perceive_node(state, router)
    analyst_node(state, router)
    scheduler_node(state, router)
    explainer_node(state, router)
    critic_node(state, router)
    assert router.calls == [
        "supervisor",
        "analyst",
        "scheduler",
        "explainer",
        "critic",
    ]
    assert router.efforts == ["minimal", "low", "low", "low", "low"]


def test_scheduler_sees_facts_and_review_notes() -> None:
    router = FakeRouter({"scheduler": [reply("[]")]})
    state = PlanState(
        request="plane",
        analysis=["billig nachts"],
        verdict=CriticVerdict(approved=False, notes=["beleg fehlt"]),
    )
    scheduler_node(state, router)
    (prompt,) = router.prompts
    assert "billig nachts" in prompt
    assert "beleg fehlt" in prompt


def test_explainer_sees_schedule() -> None:
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


def test_publish_needs_approval() -> None:
    blocked = publish_node(PlanState(request="plane", approval="pending"))
    assert blocked.get("published", False) is False
    assert blocked["error"] == "publish blocked: approval pending"


def test_publish_marks_published_when_approved() -> None:
    update = publish_node(PlanState(request="plane", approval="approved"))
    assert update["published"] is True
    assert "error" not in update
