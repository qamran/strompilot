"""Tests for Flex-Alarm triage on the watcher leg."""

from datetime import date

from strompilot.flexalarm.models import AlertCandidate, TriageVerdict
from strompilot.flexalarm.triage import judge
from strompilot.llm.client import LOW_EFFORT
from strompilot.llm.types import LlmError
from tests.fakes import FakeRouter, reply


def candidate() -> AlertCandidate:
    """Negative-price stretch the judge should love."""
    return AlertCandidate(
        kind="negative_prices",
        day=date(2026, 6, 1),
        start="11:00",
        end="14:00",
        avg_ct_kwh=-2.67,
        mean_ct_kwh=22.0,
        extreme_ct_kwh=-5.0,
        hours=3.0,
    )


def test_fire_verdict_parses_with_reason() -> None:
    router = FakeRouter({"watcher": [reply('{"fire": true, "reason": "free power"}')]})
    verdict = judge(candidate(), ["Waschmaschine"], [], router)
    assert verdict == TriageVerdict(fire=True, reason="free power")
    assert router.calls == ["watcher"]
    assert router.efforts == [LOW_EFFORT]
    assert router.temps == [0.0]


def test_skip_verdict_parses() -> None:
    router = FakeRouter({"watcher": [reply('{"fire": false, "reason": "nag"}')]})
    verdict = judge(candidate(), [], ["billig nachts"], router)
    assert verdict.fire is False


def test_prompt_carries_window_facts_and_context() -> None:
    router = FakeRouter({"watcher": [reply('{"fire": true, "reason": "ok"}')]})
    judge(candidate(), ["E-Auto"], ["frueherer Alarm"], router)
    prompt = router.prompts[0]
    assert "11:00" in prompt and "14:00" in prompt
    assert "E-Auto" in prompt
    assert "frueherer Alarm" in prompt


def test_judge_asks_for_english_reasons_when_asked() -> None:
    router = FakeRouter({"watcher": [reply('{"fire": true, "reason": "ok"}')]})
    judge(candidate(), [], [], router, lang="en")
    assert "one short English sentence" in router.prompts[0]


def test_garbage_reply_fails_closed_to_skip() -> None:
    router = FakeRouter({"watcher": [reply("MAYBE, check back later")]})
    verdict = judge(candidate(), [], [], router)
    assert verdict.fire is False
    assert "unparseable" in verdict.reason


def test_wrong_types_fail_closed_to_skip() -> None:
    router = FakeRouter({"watcher": [reply('{"fire": "yes", "reason": 7}')]})
    assert judge(candidate(), [], [], router).fire is False


def test_model_error_fails_closed_to_skip() -> None:
    router = FakeRouter({"watcher": [LlmError("baseten down")]})
    verdict = judge(candidate(), [], [], router)
    assert verdict.fire is False
    assert "triage failed" in verdict.reason
