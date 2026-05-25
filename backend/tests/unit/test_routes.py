from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.embedder import EmbedError
from app.services.llm import LLMError
from app.services.scraper import ArticleContent, ArticleError

_BASE = "http://test"
_WIKI_URL = "https://en.wikipedia.org/wiki/Test"
_FAKE_ARTICLE = ArticleContent(title="Test Article", body_text="Body text about something interesting.")
_FAKE_VECTOR = [0.1] * 384


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=_BASE) as c:
        yield c


@pytest.fixture
def happy_ingest(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.services.scraper.fetch_article", AsyncMock(return_value=_FAKE_ARTICLE))
    monkeypatch.setattr("app.services.chunker.split", MagicMock(return_value=["chunk one"]))
    monkeypatch.setattr("app.services.embedder.embed_batch", AsyncMock(return_value=[_FAKE_VECTOR]))
    monkeypatch.setattr("app.services.vector_store.recreate_and_insert", MagicMock(return_value=None))
    monkeypatch.setattr("app.services.llm.summarise", AsyncMock(return_value="A concise summary."))


# ── ingest ────────────────────────────────────────────────────────────────────

async def test_ingest_success_returns_title_and_summary(
    client: AsyncClient, happy_ingest: None
):
    resp = await client.post("/ingest", json={"url": _WIKI_URL})

    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Test Article"
    assert body["summary"] == "A concise summary."


async def test_ingest_non_wikipedia_url_returns_400(client: AsyncClient):
    with patch(
        "app.services.scraper.fetch_article",
        AsyncMock(side_effect=ArticleError("Not a Wikipedia URL")),
    ):
        resp = await client.post("/ingest", json={"url": "https://example.com/page"})

    assert resp.status_code == 400
    assert "Not a Wikipedia URL" in resp.json()["detail"]


async def test_ingest_disambiguation_returns_400(client: AsyncClient):
    with patch(
        "app.services.scraper.fetch_article",
        AsyncMock(side_effect=ArticleError("Disambiguation page — provide a more specific URL")),
    ):
        resp = await client.post("/ingest", json={"url": _WIKI_URL})

    assert resp.status_code == 400
    assert "Disambiguation" in resp.json()["detail"]


async def test_ingest_embed_failure_returns_502(client: AsyncClient):
    with patch("app.services.scraper.fetch_article", AsyncMock(return_value=_FAKE_ARTICLE)), \
         patch("app.services.chunker.split", MagicMock(return_value=["chunk"])), \
         patch("app.services.embedder.embed_batch", AsyncMock(side_effect=EmbedError("Ollama embeddings HTTP 500"))):
        resp = await client.post("/ingest", json={"url": _WIKI_URL})

    assert resp.status_code == 502
    assert "Ollama embeddings" in resp.json()["detail"]


async def test_ingest_llm_failure_returns_502(client: AsyncClient):
    with patch("app.services.scraper.fetch_article", AsyncMock(return_value=_FAKE_ARTICLE)), \
         patch("app.services.chunker.split", MagicMock(return_value=["chunk"])), \
         patch("app.services.embedder.embed_batch", AsyncMock(return_value=[_FAKE_VECTOR])), \
         patch("app.services.vector_store.recreate_and_insert", MagicMock(return_value=None)), \
         patch("app.services.llm.summarise", AsyncMock(side_effect=LLMError("LLM request timed out"))):
        resp = await client.post("/ingest", json={"url": _WIKI_URL})

    assert resp.status_code == 502
    assert "timed out" in resp.json()["detail"]


async def test_ingest_missing_url_field_returns_422(client: AsyncClient):
    resp = await client.post("/ingest", json={})
    assert resp.status_code == 422


# ── chat ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def happy_chat(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.services.vector_store.collection_exists", MagicMock(return_value=True))
    monkeypatch.setattr("app.services.embedder.embed_single", AsyncMock(return_value=_FAKE_VECTOR))
    monkeypatch.setattr("app.services.vector_store.search", MagicMock(return_value=["relevant chunk"]))
    monkeypatch.setattr("app.services.llm.answer", AsyncMock(return_value="The answer is 42."))


async def test_chat_success_returns_answer(client: AsyncClient, happy_chat: None):
    resp = await client.post("/chat", json={"question": "What is the answer?"})

    assert resp.status_code == 200
    assert resp.json()["answer"] == "The answer is 42."


async def test_chat_returns_400_when_no_article_loaded(client: AsyncClient):
    with patch("app.services.vector_store.collection_exists", MagicMock(return_value=False)):
        resp = await client.post("/chat", json={"question": "Anything?"})

    assert resp.status_code == 400
    assert "No article loaded" in resp.json()["detail"]


async def test_chat_embed_failure_returns_502(client: AsyncClient):
    with patch("app.services.vector_store.collection_exists", MagicMock(return_value=True)), \
         patch("app.services.embedder.embed_single", AsyncMock(side_effect=EmbedError("Embedding request timed out"))):
        resp = await client.post("/chat", json={"question": "Anything?"})

    assert resp.status_code == 502
    assert "Embedding request timed out" in resp.json()["detail"]


async def test_chat_llm_failure_returns_502(client: AsyncClient):
    with patch("app.services.vector_store.collection_exists", MagicMock(return_value=True)), \
         patch("app.services.embedder.embed_single", AsyncMock(return_value=_FAKE_VECTOR)), \
         patch("app.services.vector_store.search", MagicMock(return_value=["chunk"])), \
         patch("app.services.llm.answer", AsyncMock(side_effect=LLMError("LLM request timed out"))):
        resp = await client.post("/chat", json={"question": "Anything?"})

    assert resp.status_code == 502
    assert "timed out" in resp.json()["detail"]


async def test_chat_missing_question_returns_422(client: AsyncClient):
    resp = await client.post("/chat", json={})
    assert resp.status_code == 422


async def test_chat_accepts_history_in_request(client: AsyncClient, happy_chat: None):
    history = [
        {"role": "user", "content": "previous question"},
        {"role": "assistant", "content": "previous answer"},
    ]
    resp = await client.post("/chat", json={"question": "Follow up?", "history": history})

    assert resp.status_code == 200
