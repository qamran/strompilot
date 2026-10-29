"""Tests for the human approval interrupt and resume flow."""

from pathlib import Path

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from strompilot.agents.state import PlanState
from strompilot.agents.supervisor import build_graph
from strompilot.agents.workers import approve_node, publish_node
from tests.fakes import (
    ANALYST_JSON,
    CLEAN_NARRATION,
    FakeRouter,
    reply,
    stub_loader,
    thread_config,
)
from tests.test_graph import APPROVE

REQUEST: PlanState = {"request": "plane meinen Tag", "approval": "approved"}


def make_router() -> FakeRouter:
    from strompilot.llm.client import SPARK_OPEN_MODEL, WONDER_MODEL

    return FakeRouter(
        {
            "supervisor": [reply("plan")],
            "analyst": [reply(ANALYST_JSON)],
            "explainer": [reply(CLEAN_NARRATION, SPARK_OPEN_MODEL)],
            "critic": [reply(APPROVE, WONDER_MODEL)],
        }
    )


def test_approve_node_cannot_pause_outside_a_run() -> None:
    with pytest.raises(RuntimeError):
        approve_node(PlanState(request="plane"))


def test_approve_node_passes_through_decision() -> None:
    update = approve_node(PlanState(request="plane", approval="approved"))
    assert "approval" not in update
    assert any("approve" in event for event in update["audit"])


def test_publish_rejected_reports_rejection() -> None:
    blocked = publish_node(PlanState(request="plane", approval="rejected"))
    assert blocked.get("published", False) is False
    assert blocked["error"] == "publish blocked: approval rejected"


def test_run_pauses_for_approval(tmp_path: Path) -> None:
    with SqliteSaver.from_conn_string(str(tmp_path / "threads.db")) as saver:
        graph = build_graph(make_router(), stub_loader, checkpointer=saver)
        config = thread_config("t1")
        paused = graph.invoke(
            {"request": "plane meinen Tag", "approval": "pending"}, config
        )
        assert "__interrupt__" in paused
        (found,) = paused["__interrupt__"]
        assert found.value["type"] == "plan_approval"
        assert found.value["schedule"][0]["device"] == "Waschmaschine"
        assert found.value["total_cost_eur"] == 0.60
        assert "Waschmaschine" in found.value["narration"]


def test_approve_resumes_to_published(tmp_path: Path) -> None:
    with SqliteSaver.from_conn_string(str(tmp_path / "threads.db")) as saver:
        graph = build_graph(make_router(), stub_loader, checkpointer=saver)
        config = thread_config("t1")
        graph.invoke({"request": "plane meinen Tag", "approval": "pending"}, config)
        final = graph.invoke(Command(resume={"approved": True}), config)
        assert final["published"] is True
        assert final["approval"] == "approved"


def test_reject_blocks_publish(tmp_path: Path) -> None:
    with SqliteSaver.from_conn_string(str(tmp_path / "threads.db")) as saver:
        graph = build_graph(make_router(), stub_loader, checkpointer=saver)
        config = thread_config("t1")
        graph.invoke({"request": "plane meinen Tag", "approval": "pending"}, config)
        final = graph.invoke(Command(resume={"approved": False}), config)
        assert final.get("published", False) is False
        assert final["error"] == "publish blocked: approval rejected"


def test_predecided_skips_interrupt(tmp_path: Path) -> None:
    with SqliteSaver.from_conn_string(str(tmp_path / "threads.db")) as saver:
        graph = build_graph(make_router(), stub_loader, checkpointer=saver)
        final = graph.invoke(REQUEST, thread_config("t1"))
        assert "__interrupt__" not in final
        assert final["published"] is True


def test_no_checkpointer_keeps_fail_closed() -> None:
    graph = build_graph(make_router(), stub_loader)
    final = graph.invoke({"request": "plane meinen Tag", "approval": "pending"})
    assert final.get("published", False) is False
    assert final["error"] == "publish blocked: approval pending"
