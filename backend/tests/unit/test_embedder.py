from __future__ import annotations

import httpx
import pytest
import respx

from app.config import settings
from app.services.embedder import EmbedError, embed_batch, embed_single


_EMBED_URL = f"{settings.ollama_base_url}/api/embeddings"
_VECTOR_DIM = 384
_FAKE_VECTOR = [0.1] * _VECTOR_DIM


def _embed_response(vector: list[float] | None = None) -> httpx.Response:
    return httpx.Response(200, json={"embedding": vector or _FAKE_VECTOR})


async def test_embed_single_returns_384_dim_vector():
    with respx.mock:
        respx.post(_EMBED_URL).mock(return_value=_embed_response())
        result = await embed_single("some text")

    assert isinstance(result, list)
    assert len(result) == _VECTOR_DIM
    assert all(isinstance(v, float) for v in result)


async def test_embed_batch_returns_one_vector_per_input():
    texts = ["first chunk", "second chunk", "third chunk"]
    with respx.mock:
        respx.post(_EMBED_URL).mock(return_value=_embed_response())
        results = await embed_batch(texts)

    assert len(results) == len(texts)
    for vec in results:
        assert len(vec) == _VECTOR_DIM


async def test_embed_batch_empty_input_returns_empty_list():
    with respx.mock:
        results = await embed_batch([])

    assert results == []


async def test_embed_single_raises_on_ollama_server_error():
    with respx.mock:
        respx.post(_EMBED_URL).mock(return_value=httpx.Response(500))
        with pytest.raises(EmbedError, match="HTTP 500"):
            await embed_single("text")


async def test_embed_single_raises_on_timeout():
    with respx.mock:
        respx.post(_EMBED_URL).mock(side_effect=httpx.TimeoutException("timed out"))
        with pytest.raises(EmbedError, match="timed out"):
            await embed_single("text")


async def test_embed_single_raises_on_missing_embedding_key():
    with respx.mock:
        respx.post(_EMBED_URL).mock(return_value=httpx.Response(200, json={"result": []}))
        with pytest.raises(EmbedError, match="Unexpected response shape"):
            await embed_single("text")
