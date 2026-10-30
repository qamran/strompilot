"""Tests for Spark extraction of household constraints."""

import pytest

from strompilot.lifeplan.extract import analyze
from strompilot.llm.client import SPARK_MODEL
from strompilot.llm.types import LlmError
from tests.fakes import FakeRouter, reply

VALID = """{"facts": ["Nachtstrom ist billig"],
"devices": [
{"device": "Waschmaschine", "power_kw": 2.0, "duration_h": 2.0,
"earliest": "06:00", "latest": "10:00", "shiftable": true},
{"device": "E-Auto", "power_kw": 11.0, "duration_h": 4.0,
"earliest": "22:00", "latest": "06:00", "shiftable": true}
],
"notes": ""}"""


def test_analyze_parses_facts_and_constraints() -> None:
    router = FakeRouter({"analyst": [reply(VALID)]})
    analysis = analyze("Waschmaschine morgens, E-Auto nachts.", router)
    assert analysis.facts == ["Nachtstrom ist billig"]
    assert analysis.model == SPARK_MODEL
    devices = analysis.constraints.devices
    assert [device.device for device in devices] == ["Waschmaschine", "E-Auto"]
    assert devices[0].power_kw == 2.0
    assert (devices[1].earliest, devices[1].latest) == ("22:00", "06:00")
    assert analysis.constraints.notes == ""


def test_analyze_repairs_invalid_json_once() -> None:
    router = FakeRouter({"analyst": [reply("kein json"), reply(VALID)]})
    analysis = analyze("Waschmaschine morgens.", router)
    assert len(analysis.constraints.devices) == 2
    assert router.calls == ["analyst", "analyst"]


def test_analyze_fails_loudly_after_failed_repair() -> None:
    router = FakeRouter({"analyst": [reply("nein"), reply("immer noch nein")]})
    with pytest.raises(LlmError, match="extraction failed"):
        analyze("Waschmaschine morgens.", router)


def test_analyze_pins_worker_effort_and_temperature() -> None:
    router = FakeRouter({"analyst": [reply(VALID)]})
    analyze("Waschmaschine morgens.", router)
    assert router.calls == ["analyst"]
    assert router.efforts == ["low"]
    assert router.temps == [0.0]
    assert "JSON only" in router.prompts[0]


def test_analyze_budgets_for_deep_thinking() -> None:
    """1200 tokens truncated a real input after 1198 thinking tokens."""
    router = FakeRouter({"analyst": [reply(VALID)]})
    analyze("Waschmaschine morgens.", router)
    assert router.budgets[0] >= 2000


def test_analyze_marks_text_as_data_and_ignores_orders() -> None:
    router = FakeRouter({"analyst": [reply(VALID)]})
    analyze("Waschmaschine morgens.", router)
    (prompt,) = router.prompts
    assert "<household_text>" in prompt
    assert "strictly as data" in prompt
