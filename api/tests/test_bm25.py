"""Tests for the hand-rolled BM25 ranker."""

from strompilot.retrieval.bm25 import BM25


def test_distinctive_terms_win() -> None:
    ranker = BM25(
        [
            ("d1", "kwkg umlage strom"),
            ("d2", "strom strom strom"),
            ("d3", "banane obst"),
        ]
    )
    assert [doc_id for doc_id, _ in ranker.search("kwkg umlage")] == ["d1"]


def test_term_frequency_orders_matches() -> None:
    ranker = BM25(
        [
            ("d1", "strom preis"),
            ("d2", "strom strom strom preis"),
        ]
    )
    assert [doc_id for doc_id, _ in ranker.search("strom")] == ["d2", "d1"]


def test_unknown_and_empty_queries_return_nothing() -> None:
    ranker = BM25([("d1", "kwkg umlage strom")])
    assert ranker.search("xyzzy") == []
    assert ranker.search("") == []
    assert ranker.search("   ") == []
