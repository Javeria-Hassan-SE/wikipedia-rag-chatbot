from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

pytestmark = pytest.mark.integration

_ARTICLE_URL = "https://en.wikipedia.org/wiki/Ada_Lovelace"
_QUESTION = "What is Ada Lovelace known for?"
_FOLLOWUP = "When was she born?"


async def test_full_rag_pipeline():
    # 180s covers slow CPU inference and embedding all article chunks on a 3B model
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=180,
    ) as client:
        ingest_resp = await client.post("/ingest", json={"url": _ARTICLE_URL})
        assert ingest_resp.status_code == 200, ingest_resp.text

        ingest_data = ingest_resp.json()
        assert ingest_data["title"] == "Ada Lovelace"
        assert len(ingest_data["summary"]) > 50

        chat_resp = await client.post("/chat", json={"question": _QUESTION})
        assert chat_resp.status_code == 200, chat_resp.text

        answer = chat_resp.json()["answer"]
        assert isinstance(answer, str)
        assert len(answer) > 20


async def test_chat_before_ingest_returns_400():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=10,
    ) as client:
        resp = await client.post("/chat", json={"question": "Anything?"})

    assert resp.status_code == 400
    assert "No article loaded" in resp.json()["detail"]


async def test_multi_turn_chat_accepts_history():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=180,
    ) as client:
        ingest_resp = await client.post("/ingest", json={"url": _ARTICLE_URL})
        assert ingest_resp.status_code == 200, ingest_resp.text

        first = await client.post("/chat", json={"question": _QUESTION})
        assert first.status_code == 200

        history = [
            {"role": "user", "content": _QUESTION},
            {"role": "assistant", "content": first.json()["answer"]},
        ]
        followup = await client.post(
            "/chat", json={"question": _FOLLOWUP, "history": history}
        )
        assert followup.status_code == 200
        assert len(followup.json()["answer"]) > 10
