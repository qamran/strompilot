"""Tests for the model router: legs, fallback, spend, and rails."""

import pytest

from strompilot.agents.guards import GuardError
from strompilot.agents.router import ModelRouter
from strompilot.llm.client import (
    SPARK_MODEL,
    SPARK_OPEN_MODEL,
    WONDER_MODEL,
)
from strompilot.llm.types import LlmError, Message
from tests.fakes import StubLeg, reply


def make_router(spark: StubLeg, wonder: StubLeg, open_leg: StubLeg) -> ModelRouter:
    return ModelRouter(
        {
            "supervisor": (spark, None),
            "analyst": (spark, None),
            "scheduler": (spark, None),
            "explainer": (open_leg, spark),
            "critic": (wonder, spark),
        }
    )


def test_analyst_runs_on_spark_with_priced_spend() -> None:
    spark = StubLeg(SPARK_MODEL, [reply("facts", SPARK_MODEL, 1000, 100)])
    router = make_router(
        spark, StubLeg(WONDER_MODEL, []), StubLeg(SPARK_OPEN_MODEL, [])
    )
    result = router.chat("analyst", [Message(role="user", content="analyse")], 500)
    assert result.content == "facts"
    assert len(spark.calls) == 1
    (entry,) = router.spend_log
    assert entry.worker == "analyst"
    assert entry.requested_model == SPARK_MODEL
    assert entry.actual_model == SPARK_MODEL
    assert (entry.input_tokens, entry.output_tokens) == (1000, 100)
    assert entry.cost_usd == pytest.approx(0.001675)


def test_explainer_runs_on_baseten_with_unpriced_spend() -> None:
    open_leg = StubLeg(SPARK_OPEN_MODEL, [reply("text", SPARK_OPEN_MODEL)])
    router = make_router(StubLeg(SPARK_MODEL, []), StubLeg(WONDER_MODEL, []), open_leg)
    result = router.chat("explainer", [Message(role="user", content="narrate")], 500)
    assert result.content == "text"
    (entry,) = router.spend_log
    assert entry.requested_model == SPARK_OPEN_MODEL
    assert entry.actual_model == SPARK_OPEN_MODEL
    assert entry.cost_usd is None


def test_critic_runs_on_wonder() -> None:
    wonder = StubLeg(WONDER_MODEL, [reply("{}", WONDER_MODEL, 1000, 100)])
    router = make_router(
        StubLeg(SPARK_MODEL, []), wonder, StubLeg(SPARK_OPEN_MODEL, [])
    )
    router.chat("critic", [Message(role="user", content="judge")], 500)
    assert len(wonder.calls) == 1
    (entry,) = router.spend_log
    assert entry.actual_model == WONDER_MODEL
    assert entry.cost_usd == pytest.approx(0.006)


def test_baseten_failure_falls_back_to_spark() -> None:
    open_leg = StubLeg(SPARK_OPEN_MODEL, [LlmError("baseten down")])
    spark = StubLeg(SPARK_MODEL, [reply("fallback text", SPARK_MODEL)])
    router = make_router(spark, StubLeg(WONDER_MODEL, []), open_leg)
    result = router.chat("explainer", [Message(role="user", content="narrate")], 500)
    assert result.content == "fallback text"
    (entry,) = router.spend_log
    assert entry.requested_model == SPARK_OPEN_MODEL
    assert entry.actual_model == SPARK_MODEL


def test_wonder_failure_falls_back_to_spark() -> None:
    wonder = StubLeg(WONDER_MODEL, [LlmError("wonder down")])
    spark = StubLeg(SPARK_MODEL, [reply("{}", SPARK_MODEL)])
    router = make_router(spark, wonder, StubLeg(SPARK_OPEN_MODEL, []))
    router.chat("critic", [Message(role="user", content="judge")], 500)
    (entry,) = router.spend_log
    assert entry.requested_model == WONDER_MODEL
    assert entry.actual_model == SPARK_MODEL


def test_spark_leg_retries_once_then_fails_loudly() -> None:
    spark = StubLeg(SPARK_MODEL, [LlmError("boom"), LlmError("boom")])
    router = make_router(
        spark, StubLeg(WONDER_MODEL, []), StubLeg(SPARK_OPEN_MODEL, [])
    )
    with pytest.raises(LlmError, match="boom"):
        router.chat("analyst", [Message(role="user", content="x")], 500)
    assert len(spark.calls) == 2
    assert router.spend_log == []


def test_double_failure_raises_without_spend() -> None:
    open_leg = StubLeg(SPARK_OPEN_MODEL, [LlmError("baseten down")])
    spark = StubLeg(SPARK_MODEL, [LlmError("spark down")])
    router = make_router(spark, StubLeg(WONDER_MODEL, []), open_leg)
    with pytest.raises(LlmError, match="spark down"):
        router.chat("explainer", [Message(role="user", content="x")], 500)
    assert router.spend_log == []


def test_unknown_worker_fails_loudly() -> None:
    router = make_router(
        StubLeg(SPARK_MODEL, []),
        StubLeg(WONDER_MODEL, []),
        StubLeg(SPARK_OPEN_MODEL, []),
    )
    with pytest.raises(ValueError, match="janitor"):
        router.chat("janitor", [Message(role="user", content="x")], 500)


def test_from_keys_pins_production_assignments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    models: list[str] = []

    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "x"}}]}

    def fake_post(
        url: str, headers: dict[str, str], json: dict[str, object], timeout: float
    ) -> FakeResponse:
        del url, headers, timeout
        model = json["model"]
        assert isinstance(model, str)
        models.append(model)
        return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    router = ModelRouter.from_keys("meta-key", "baseten-key")
    for worker in ["supervisor", "analyst", "explainer", "critic"]:
        router.chat(worker, [Message(role="user", content="x")], 10)
    assert models == [
        SPARK_MODEL,
        SPARK_MODEL,
        SPARK_OPEN_MODEL,
        WONDER_MODEL,
    ]


def test_from_keys_explainer_falls_back_to_spark(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    models: list[str] = []

    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "x"}}]}

    def fake_post(
        url: str, headers: dict[str, str], json: dict[str, object], timeout: float
    ) -> FakeResponse:
        del headers, timeout
        if "baseten" in url:
            raise httpx.ConnectError("baseten down")
        model = json["model"]
        assert isinstance(model, str)
        models.append(model)
        return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    router = ModelRouter.from_keys("meta-key", "baseten-key")
    router.chat("explainer", [Message(role="user", content="x")], 10)
    assert models == [SPARK_MODEL]


def test_new_run_resets_spend_and_stall_tracking() -> None:
    spark = StubLeg(SPARK_MODEL, [reply("a")] * 4)
    router = make_router(
        spark, StubLeg(WONDER_MODEL, []), StubLeg(SPARK_OPEN_MODEL, [])
    )
    messages = [Message(role="user", content="same")]
    router.chat("analyst", messages, 500)
    router.chat("analyst", messages, 500)
    router.new_run()
    assert router.spend_log == []
    router.chat("analyst", messages, 500)
    router.chat("analyst", messages, 500)
    assert len(router.spend_log) == 2


def test_repeated_identical_calls_pause_the_run() -> None:
    spark = StubLeg(SPARK_MODEL, [reply("a"), reply("a"), reply("a")])
    router = make_router(
        spark, StubLeg(WONDER_MODEL, []), StubLeg(SPARK_OPEN_MODEL, [])
    )
    messages = [Message(role="user", content="same")]
    router.chat("analyst", messages, 500)
    router.chat("analyst", messages, 500)
    with pytest.raises(GuardError, match="repeated"):
        router.chat("analyst", messages, 500)


def test_changed_call_resets_the_stall_tracker() -> None:
    spark = StubLeg(SPARK_MODEL, [reply("a"), reply("b"), reply("c")])
    router = make_router(
        spark, StubLeg(WONDER_MODEL, []), StubLeg(SPARK_OPEN_MODEL, [])
    )
    router.chat("analyst", [Message(role="user", content="one")], 500)
    router.chat("analyst", [Message(role="user", content="two")], 500)
    router.chat("analyst", [Message(role="user", content="one")], 500)
    assert len(router.spend_log) == 3


def test_router_forwards_reasoning_effort_to_both_legs() -> None:
    open_leg = StubLeg(SPARK_OPEN_MODEL, [LlmError("baseten down")])
    spark = StubLeg(SPARK_MODEL, [reply("fallback text", SPARK_MODEL)])
    router = make_router(spark, StubLeg(WONDER_MODEL, []), open_leg)
    router.chat(
        "explainer",
        [Message(role="user", content="x")],
        500,
        reasoning_effort="low",
    )
    assert open_leg.efforts == ["low"]
    assert spark.efforts == ["low"]


def test_router_forwards_temperature_to_both_legs() -> None:
    open_leg = StubLeg(SPARK_OPEN_MODEL, [LlmError("baseten down")])
    spark = StubLeg(SPARK_MODEL, [reply("fallback text", SPARK_MODEL)])
    router = make_router(spark, StubLeg(WONDER_MODEL, []), open_leg)
    router.chat(
        "explainer",
        [Message(role="user", content="x")],
        500,
        temperature=0.0,
    )
    assert open_leg.temps == [0.0]
    assert spark.temps == [0.0]


def test_router_strips_personal_data_before_legs() -> None:
    spark = StubLeg(SPARK_MODEL, [reply("ok")])
    router = make_router(
        spark, StubLeg(WONDER_MODEL, []), StubLeg(SPARK_OPEN_MODEL, [])
    )
    router.chat(
        "analyst",
        [Message(role="user", content="Mail max@example.de, bitte planen")],
        500,
    )
    (sent,) = spark.calls
    assert sent[0].content == "Mail [E-Mail entfernt], bitte planen"


def test_cost_rail_trips_after_logging_the_call() -> None:
    spark = StubLeg(SPARK_MODEL, [reply("big", SPARK_MODEL, 300_000, 0)])
    router = make_router(
        spark, StubLeg(WONDER_MODEL, []), StubLeg(SPARK_OPEN_MODEL, [])
    )
    with pytest.raises(GuardError, match="cost rail"):
        router.chat("analyst", [Message(role="user", content="x")], 500)
    assert len(router.spend_log) == 1
