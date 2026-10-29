"""Spark Open re-ranker on Baseten (OpenAI-compatible chat)."""

import re

import httpx

BASE_URL = "https://inference.baseten.co/v1"
MODEL = "meta-models/muse-spark-open-1026"
TIMEOUT_SECONDS = 60.0
# Generous ceiling: the model reasons before answering, and a cut-off
# reply would leave content empty. Equal fallback scores keep BM25 order
# because the rerank sort is stable.
MAX_TOKENS = 1000

_SCORE_LINE = re.compile(r"^\s*(\d+)\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*$")


class BasetenClient:
    """Scores passages through Spark Open on Baseten."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def rerank_scores(self, query: str, texts: list[str]) -> list[float]:
        """Return one 0-10 relevance score per passage."""
        numbered = "\n".join(f"{n}: {text}" for n, text in enumerate(texts))
        response = httpx.post(
            f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "Rank each passage for the query. Reply "
                        "with one `index: score` line per passage, score "
                        "0 to 10.",
                    },
                    {
                        "role": "user",
                        "content": f"Query: {query}\n{numbered}",
                    },
                ],
                "max_tokens": MAX_TOKENS,
            },
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            return [0.0] * len(texts)
        return self._parse_scores(str(content), len(texts))

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
