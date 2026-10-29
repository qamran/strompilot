"""Sentence chunker for corpus documents."""

import re

from pydantic import BaseModel

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


class Chunk(BaseModel):
    """One citable chunk carrying its document source."""

    chunk_id: str
    doc_id: str
    title: str
    text: str
    source_name: str
    source_url: str


def chunk_text(
    doc_id: str,
    title: str,
    text: str,
    source_name: str = "",
    source_url: str = "",
    max_chars: int = 600,
) -> list[Chunk]:
    """Split text into sentence chunks capped at max_chars each."""
    sentences = [
        sentence.strip()
        for sentence in _SENTENCE_SPLIT.split(text.strip())
        if sentence.strip()
    ]
    chunks: list[Chunk] = []
    current: list[str] = []
    current_len = 0
    for sentence in sentences:
        extra = len(sentence) + (1 if current else 0)
        if current and current_len + extra > max_chars:
            chunks.append(
                _make_chunk(
                    doc_id, title, source_name, source_url, len(chunks), current
                )
            )
            current = []
            current_len = 0
        current.append(sentence)
        current_len += len(sentence) + 1
    if current:
        chunks.append(
            _make_chunk(doc_id, title, source_name, source_url, len(chunks), current)
        )
    return chunks


def _make_chunk(
    doc_id: str,
    title: str,
    source_name: str,
    source_url: str,
    index: int,
    sentences: list[str],
) -> Chunk:
    return Chunk(
        chunk_id=f"{doc_id}#{index}",
        doc_id=doc_id,
        title=title,
        text=" ".join(sentences),
        source_name=source_name,
        source_url=source_url,
    )
