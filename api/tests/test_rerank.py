"""Tests for the re-ranker and the Baseten client."""

import pytest

from strompilot.retrieval.baseten import BasetenClient
from strompilot.retrieval.retriever import Hit, Retriever


class ReversingClient:
    """Fake re-ranker that reverses the candidate order."""

    def rerank_scores(self, query: str, texts: list[str]) -> list[float]:
        del query
        return [float(n) for n in range(len(texts))]


def make_hits() -> list[Hit]:
    return [
        Hit(
            chunk_id=f"c{n}",
            doc_id=f"d{n}",
            title=f"T{n}",
            text=f"text {n}",
            source_name="S",
            source_url="https://example.com",
            score=10.0 - n,
        )
        for n in range(3)
    ]


def test_rerank_applies_client_order() -> None:
    retriever = Retriever([])
    ranked = retriever.rerank("frage", make_hits(), ReversingClient())
    assert [hit.chunk_id for hit in ranked] == ["c2", "c1", "c0"]
    assert ranked[0].title == "T2"
    assert ranked[0].source_url == "https://example.com"


def test_baseten_client_posts_chat_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, object]:
            return {
                "choices": [
                    {"message": {"content": "0: 9\n1: 4\n"}},
                ]
            }

    def fake_post(
        url: str, headers: dict[str, str], json: dict[str, object], timeout: float
    ) -> FakeResponse:
        captured["url"] = url
        captured["model"] = json["model"]
        captured["messages"] = json["messages"]
        assert headers["Authorization"].startswith("Bearer ")
        assert timeout > 0
        return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    client = BasetenClient(api_key="test-key")
    scores = client.rerank_scores("frage", ["eins", "zwei"])
    assert captured["url"] == "https://inference.baseten.co/v1/chat/completions"
    assert captured["model"] == "meta-models/muse-spark-open-1026"
    assert scores == [9.0, 4.0]


def test_baseten_client_falls_back_on_garbage() -> None:
    client = BasetenClient(api_key="test-key")
    scores = client._parse_scores("keine zahlen hier", 3)
    assert scores == [0.0, 0.0, 0.0]


def test_baseten_client_falls_back_on_broken_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class EmptyResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, object]:
            return {"choices": []}

    def fake_post(
        url: str, headers: dict[str, str], json: dict[str, object], timeout: float
    ) -> EmptyResponse:
        del url, headers, json, timeout
        return EmptyResponse()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    client = BasetenClient(api_key="test-key")
    assert client.rerank_scores("frage", ["eins", "zwei"]) == [0.0, 0.0]


def test_baseten_client_clamps_scores_to_scale() -> None:
    client = BasetenClient(api_key="test-key")
    assert client._parse_scores("0: 999", 1) == [10.0]
