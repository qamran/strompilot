"""End-to-end graph runs with a scripted router."""

import pytest

from strompilot.agents.supervisor import build_graph
from strompilot.llm.client import SPARK_MODEL, SPARK_OPEN_MODEL, WONDER_MODEL
from strompilot.llm.types import LlmError
from tests.fakes import ANALYST_JSON, CLEAN_NARRATION, FakeRouter, reply, stub_loader

APPROVE = '{"approved": true, "notes": []}'
VETO = '{"approved": false, "notes": ["beleg fehlt"]}'


def happy_router() -> FakeRouter:
    return FakeRouter(
        {
            "supervisor": [reply("plan")],
            "analyst": [reply(ANALYST_JSON)],
            "explainer": [reply(CLEAN_NARRATION, SPARK_OPEN_MODEL)],
            "critic": [reply(APPROVE, WONDER_MODEL)],
        }
    )


def test_happy_path_publishes() -> None:
    graph = build_graph(happy_router(), stub_loader)
    final = graph.invoke({"request": "plane meinen Tag", "approval": "approved"})
    assert final["published"] is True
    assert final["iterations"] == 1
    assert final["narration"] == CLEAN_NARRATION
    assert final["schedule"][0]["start"] == "02:00"
    assert final["total_cost_eur"] == 0.60
    assert final["violations"] == []
    assert len(final["citations"]) >= 3
    assert final["attribution"] == {
        "intent": SPARK_MODEL,
        "analysis": SPARK_MODEL,
        "constraints": SPARK_MODEL,
        "schedule": "deterministic",
        "narration": SPARK_OPEN_MODEL,
        "verdict": WONDER_MODEL,
    }
    nodes = ["perceive", "analyst", "scheduler", "explainer", "critic"]
    for node in nodes:
        assert any(node in event for event in final["audit"]), node


def test_veto_loops_once_then_publishes() -> None:
    router = FakeRouter(
        {
            "supervisor": [reply("plan")],
            "analyst": [reply(ANALYST_JSON)],
            "explainer": [
                reply(CLEAN_NARRATION, SPARK_OPEN_MODEL),
                reply(CLEAN_NARRATION, SPARK_OPEN_MODEL),
            ],
            "critic": [reply(VETO, WONDER_MODEL), reply(APPROVE, WONDER_MODEL)],
        }
    )
    graph = build_graph(router, stub_loader)
    final = graph.invoke({"request": "plane meinen Tag", "approval": "approved"})
    assert final["published"] is True
    assert final["iterations"] == 2
    scheduled = [event for event in final["audit"] if "scheduler" in event]
    assert len(scheduled) == 2


def test_review_cap_ends_with_error() -> None:
    router = FakeRouter(
        {
            "supervisor": [reply("plan")],
            "analyst": [reply(ANALYST_JSON)],
            "explainer": [reply(CLEAN_NARRATION, SPARK_OPEN_MODEL)] * 3,
            "critic": [reply(VETO, WONDER_MODEL)] * 3,
        }
    )
    graph = build_graph(router, stub_loader)
    final = graph.invoke({"request": "plane meinen Tag", "approval": "approved"})
    assert final.get("published", False) is False
    assert final["error"] == "review cap reached"
    assert final["iterations"] == 3


def test_off_topic_ends_after_perceive() -> None:
    router = FakeRouter({"supervisor": [reply("other")]})
    graph = build_graph(router, stub_loader)
    final = graph.invoke({"request": "erzaehl einen Witz", "approval": "approved"})
    assert "analysis" not in final
    assert final.get("published", False) is False
    assert router.calls == ["supervisor"]


def test_pending_approval_blocks_publish() -> None:
    graph = build_graph(happy_router(), stub_loader)
    final = graph.invoke({"request": "plane meinen Tag", "approval": "pending"})
    assert final.get("published", False) is False
    assert final["error"] == "publish blocked: approval pending"


def test_extraction_error_aborts_the_run() -> None:
    router = FakeRouter(
        {
            "supervisor": [reply("plan")],
            "analyst": [reply("nein"), reply("nein")],
        }
    )
    graph = build_graph(router, stub_loader)
    with pytest.raises(LlmError, match="extraction failed"):
        graph.invoke({"request": "plane meinen Tag", "approval": "approved"})
