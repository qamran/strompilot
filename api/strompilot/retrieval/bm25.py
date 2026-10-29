"""Small BM25 ranker over tokenized texts (Robertson / Sparck Jones)."""

import math
import re

_TOKEN = re.compile(r"[a-zäöüß0-9]+")

K1 = 1.2
B = 0.75

STOPWORDS = frozenset(
    {
        "aber",
        "als",
        "am",
        "an",
        "auch",
        "auf",
        "aus",
        "bei",
        "beim",
        "bin",
        "bis",
        "da",
        "damit",
        "dann",
        "das",
        "dass",
        "dein",
        "dem",
        "den",
        "der",
        "des",
        "die",
        "dies",
        "doch",
        "durch",
        "ein",
        "eine",
        "einer",
        "eines",
        "er",
        "es",
        "etwas",
        "für",
        "habe",
        "haben",
        "hier",
        "ich",
        "ihr",
        "ihre",
        "im",
        "in",
        "ist",
        "jede",
        "jeder",
        "kann",
        "kein",
        "man",
        "mehr",
        "mein",
        "mit",
        "nach",
        "nicht",
        "noch",
        "nun",
        "nur",
        "oder",
        "sehr",
        "sein",
        "sich",
        "sie",
        "sind",
        "so",
        "sondern",
        "und",
        "uns",
        "unser",
        "vom",
        "von",
        "vor",
        "war",
        "was",
        "wegen",
        "weil",
        "weiter",
        "welche",
        "wenn",
        "wer",
        "werden",
        "wie",
        "wieder",
        "wird",
        "wo",
        "zu",
        "zum",
        "zur",
        "über",
    }
)


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens without German stopwords."""
    return [token for token in _TOKEN.findall(text.lower()) if token not in STOPWORDS]


class BM25:
    """In-memory BM25 index over (id, text) pairs."""

    def __init__(self, documents: list[tuple[str, str]]) -> None:
        self._doc_ids = [doc_id for doc_id, _ in documents]
        self._term_freqs: list[dict[str, int]] = []
        doc_freq: dict[str, int] = {}
        total_len = 0
        for _, text in documents:
            tokens = tokenize(text)
            freq: dict[str, int] = {}
            for token in tokens:
                freq[token] = freq.get(token, 0) + 1
            self._term_freqs.append(freq)
            total_len += len(tokens)
            for token in freq:
                doc_freq[token] = doc_freq.get(token, 0) + 1
        count = len(documents)
        self._avg_len = total_len / count if count else 0.0
        self._idf = {
            token: math.log(1 + (count - hits + 0.5) / (hits + 0.5))
            for token, hits in doc_freq.items()
        }

    def search(self, query: str, k: int = 5) -> list[tuple[str, float]]:
        """Return up to k (id, score) pairs with positive scores."""
        tokens = tokenize(query)
        if not tokens or self._avg_len == 0:
            return []
        scored: list[tuple[str, float]] = []
        for index, doc_id in enumerate(self._doc_ids):
            freq = self._term_freqs[index]
            doc_len = sum(freq.values())
            score = 0.0
            for token in set(tokens):
                count = freq.get(token, 0)
                if count == 0:
                    continue
                denom = count + K1 * (1 - B + B * doc_len / self._avg_len)
                score += self._idf[token] * count * (K1 + 1) / denom
            if score > 0:
                scored.append((doc_id, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:k]
