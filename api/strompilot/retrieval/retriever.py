"""Corpus index with BM25 retrieval and LLM re-ranking."""

from typing import Protocol

from pydantic import BaseModel

from strompilot.retrieval.bm25 import BM25
from strompilot.retrieval.chunker import Chunk, chunk_text
from strompilot.retrieval.corpus import Document


class Hit(BaseModel):
    """One retrieved chunk with its citation and score."""

    chunk_id: str
    doc_id: str
    title: str
    text: str
    source_name: str
    source_url: str
    score: float


class RerankClient(Protocol):
    """Scores candidate texts for a query, highest first."""

    def rerank_scores(self, query: str, texts: list[str]) -> list[float]: ...


class Retriever:
    """Chunked corpus with BM25 search plus optional re-ranking."""

    def __init__(self, documents: list[Document]) -> None:
        self._chunks: list[Chunk] = []
        for doc in documents:
            self._chunks.extend(
                chunk_text(doc.id, doc.title, doc.body, doc.source_name, doc.source_url)
            )
        self._ranker = BM25(
            [(chunk.chunk_id, f"{chunk.title} {chunk.text}") for chunk in self._chunks]
        )
        self._by_id = {chunk.chunk_id: chunk for chunk in self._chunks}

    def retrieve(self, query: str, k: int = 5) -> list[Hit]:
        """Return up to k BM25 hits for a query."""
        hits: list[Hit] = []
        for chunk_id, score in self._ranker.search(query, k):
            chunk = self._by_id[chunk_id]
            hits.append(
                Hit(
                    chunk_id=chunk.chunk_id,
                    doc_id=chunk.doc_id,
                    title=chunk.title,
                    text=chunk.text,
                    source_name=chunk.source_name,
                    source_url=chunk.source_url,
                    score=score,
                )
            )
        return hits

    def rerank(self, query: str, hits: list[Hit], client: RerankClient) -> list[Hit]:
        """Reorder hits by client scores, keeping input order on mismatch."""
        if not hits:
            return []
        scores = client.rerank_scores(query, [hit.text for hit in hits])
        if len(scores) != len(hits):
            return hits
        ranked = sorted(zip(hits, scores), key=lambda pair: pair[1], reverse=True)
        return [hit.model_copy(update={"score": score}) for hit, score in ranked]
