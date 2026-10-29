"""Tests for the sentence chunker."""

from strompilot.retrieval.chunker import chunk_text


def test_short_text_yields_one_chunk() -> None:
    chunks = chunk_text("doc1", "Titel", "Ein kurzer Satz.", max_chars=600)
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "doc1#0"
    assert chunks[0].doc_id == "doc1"
    assert chunks[0].text == "Ein kurzer Satz."


def test_long_text_splits_on_sentences() -> None:
    text = " ".join(f"Dies ist Satz Nummer {n}." for n in range(50))
    chunks = chunk_text("doc9", "Lang", text, max_chars=200)
    assert len(chunks) > 1
    assert all(len(chunk.text) <= 200 for chunk in chunks)
    assert [chunk.chunk_id for chunk in chunks] == [
        f"doc9#{n}" for n in range(len(chunks))
    ]
    joined = " ".join(chunk.text for chunk in chunks)
    assert "Satz Nummer 0." in joined
    assert "Satz Nummer 49." in joined


def test_empty_text_yields_no_chunks() -> None:
    assert chunk_text("doc0", "Leer", "   ", max_chars=600) == []
