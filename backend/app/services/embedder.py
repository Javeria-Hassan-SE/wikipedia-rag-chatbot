from __future__ import annotations

import httpx

from app.config import settings


class EmbedError(Exception):
    pass


async def embed_single(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=60) as client:
        return await _call_ollama(client, text)


async def embed_batch(texts: list[str]) -> list[list[float]]:
    async with httpx.AsyncClient(timeout=60) as client:
        results = []
        for text in texts:
            results.append(await _call_ollama(client, text))
        return results


async def _call_ollama(client: httpx.AsyncClient, text: str) -> list[float]:
    url = f"{settings.ollama_base_url}/api/embeddings"
    payload = {"model": settings.embed_model, "prompt": text}
    try:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()["embedding"]
    except httpx.TimeoutException as exc:
        raise EmbedError("Embedding request timed out") from exc
    except httpx.HTTPStatusError as exc:
        raise EmbedError(f"Ollama embeddings HTTP {exc.response.status_code}") from exc
    except (KeyError, TypeError) as exc:
        raise EmbedError("Unexpected response shape from Ollama embeddings") from exc
