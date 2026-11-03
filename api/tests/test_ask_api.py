"""Tests for the Ask-Why retrieval API."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import strompilot.main as main_module
from strompilot.main import app, get_ask_router
from tests.fakes import FakeRouter, reply

from .auth_helpers import sign_in


class _FakeRerank:
    """Deterministic re-ranker: keeps BM25 order with descending scores."""

    def __init__(self, api_key: str, fallback: object = None) -> None:
        self.api_key = api_key
        self.fallback = fallback

    def rerank_scores(self, query: str, texts: list[str]) -> list[float]:
        return [float(len(texts) - n) for n in range(len(texts))]


@pytest.fixture
def ask_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Signed-in client with scripted answers and a fake re-ranker."""
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    monkeypatch.setattr(main_module, "BasetenClient", _FakeRerank)
    router = FakeRouter({"ask": [reply("Weil Umlagen anfallen.", "muse-spark-open")]})
    app.dependency_overrides[get_ask_router] = lambda: router
    client = TestClient(app)
    sign_in(client, "h1")
    yield client
    app.dependency_overrides.clear()


def test_ask_returns_answer_with_citations(ask_setup: TestClient) -> None:
    response = ask_setup.get("/ask?household_id=h1&q=KWKG%20Umlage&lang=de")
    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "Weil Umlagen anfallen."
    assert payload["model"] == "muse-spark-open"
    assert len(payload["citations"]) >= 1
    first = payload["citations"][0]
    assert first["source_url"].startswith("http")
    assert "KWKG" in first["title"] or "kwkg" in first["source_name"].lower()


def test_ask_without_hits_answers_gracefully(ask_setup: TestClient) -> None:
    response = ask_setup.get("/ask?household_id=h1&q=xqzvwxplk&lang=en")
    assert response.status_code == 200
    payload = response.json()
    assert payload["citations"] == []
    assert payload["answer"] != ""


def test_ask_rejects_blank_question(ask_setup: TestClient) -> None:
    response = ask_setup.get("/ask?household_id=h1&q=%20%20")
    assert response.status_code == 422


def test_ask_needs_model_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    client = TestClient(app)
    sign_in(client, "h1")
    response = client.get("/ask?household_id=h1&q=KWKG")
    assert response.status_code == 500
