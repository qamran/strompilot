"""Spark Open re-ranker on Baseten (OpenAI-compatible chat)."""

import re

from strompilot.llm.client import (
    BASETEN_BASE_URL,
    LOW_EFFORT,
    SPARK_OPEN_MODEL,
    ChatClient,
)
from strompilot.llm.types import LlmError, Message

# Generous ceiling: the model reasons before answering, and a cut-off
# reply would leave content empty. Equal fallback scores keep BM25 order
# because the rerank sort is stable.
MAX_TOKENS = 1000

_SCORE_LINE = re.compile(r"^\s*(\d+)\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*$")


class BasetenClient:
    """Scores passages through Spark Open on Baseten."""

    def __init__(self, api_key: str, fallback: ChatClient | None = None) -> None:
        self._client = ChatClient(BASETEN_BASE_URL, api_key, SPARK_OPEN_MODEL)
        self._fallback = fallback

    def rerank_scores(self, query: str, texts: list[str]) -> list[float]:
        """Return one 0-10 relevance score per passage.

        A Baseten failure retries on the Spark fallback when one is
        configured. Any remaining failure degrades to equal zeros,
        which keeps BM25 order because the rerank sort is stable.
        """
        numbered = "\n".join(f"{n}: {text}" for n, text in enumerate(texts))
        messages = [
            Message(
                role="system",
                content="Rank each passage for the query. Reply "
                "with one `index: score` line per passage, score "
                "0 to 10.",
            ),
            Message(role="user", content=f"Query: {query}\n{numbered}"),
        ]
        try:
            result = self._client.chat(messages, MAX_TOKENS, LOW_EFFORT)
        except LlmError:
            if self._fallback is None:
                return [0.0] * len(texts)
            try:
                result = self._fallback.chat(messages, MAX_TOKENS, LOW_EFFORT)
            except LlmError:
                return [0.0] * len(texts)
        return self._parse_scores(result.content, len(texts))

    def _parse_scores(self, content: str, count: int) -> list[float]:
        """Parse `index: score` lines, clamped to 0-10, missing entries zero."""
        scores = [0.0] * count
        for line in content.splitlines():
            match = _SCORE_LINE.match(line)
            if not match:
                continue
            index = int(match.group(1))
            if 0 <= index < count:
                scores[index] = min(max(float(match.group(2)), 0.0), 10.0)
        return scores
