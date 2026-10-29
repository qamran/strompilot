"""Tests for the rule corpus, index, and golden queries."""

from strompilot.retrieval.corpus import load_corpus
from strompilot.retrieval.retriever import Retriever

GOLDEN = [
    ("Wie hoch ist die KWKG-Umlage 2026?", "kwkg-umlage-2026"),
    ("Offshore-Netzumlage Cent 2026", "offshore-umlage-2026"),
    ("§19 StromNEV Umlage Haushalte", "stromnev-umlage-2026"),
    ("Stromsteuer Kilowattstunde", "stromsteuer"),
    ("Konzessionsabgabe Großstadt Gemeindegröße", "konzessionsabgabe"),
    ("H25 Standardlastprofil Haushalte 2025", "h25-profile"),
    ("Day-Ahead Auktion Gate Closure 12 Uhr", "epex-auktion"),
    ("dynamische Tarife Pflicht Versorger", "dynamische-tarife-pflicht"),
]

NEGATIVE = [
    "Pizza backen mit Käse überbacken",
    "Bundesliga Tabelle Ergebnisse Spieltag",
    "Katzenfutter Test Nassfutter",
]


def test_corpus_holds_twenty_sourced_documents() -> None:
    documents = load_corpus()
    assert len(documents) == 20
    ids = [doc.id for doc in documents]
    assert len(set(ids)) == 20
    for doc in documents:
        assert doc.title
        assert doc.body
        assert doc.source_name
        assert doc.source_url.startswith("http")


def test_golden_queries_hit_top_rank_with_citations() -> None:
    retriever = Retriever(load_corpus())
    for query, expected_id in GOLDEN:
        hits = retriever.retrieve(query, k=3)
        assert hits, query
        assert hits[0].doc_id == expected_id, query
        assert hits[0].title
        assert hits[0].source_url.startswith("http")


def test_negative_queries_return_nothing() -> None:
    retriever = Retriever(load_corpus())
    for query in NEGATIVE:
        assert retriever.retrieve(query, k=3) == [], query
