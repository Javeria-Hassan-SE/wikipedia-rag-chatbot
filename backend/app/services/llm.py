from __future__ import annotations

import httpx

from app.config import settings
from app.models import ChatMessage


class LLMError(Exception):
    pass


_SUMMARISE_SYSTEM = (
    "You are a summarisation assistant. "
    "Produce a 3–5 sentence summary of the provided article text. "
    "Be factual and concise."
)

_ANSWER_SYSTEM = """\
You are a helpful assistant answering questions about a Wikipedia article.
Answer using ONLY the information in the context provided below.
If the answer cannot be found in the context, respond with:
"I don't have enough information in the article to answer that."
Do not use your general knowledge.

Context:
{context}"""

# LLM responses on a 3B model at CPU speeds can take up to 2 minutes for
# longer articles — 120s keeps the connection alive without blocking forever.
_LLM_TIMEOUT = 120


async def summarise(text: str) -> str:
    messages = [
        {"role": "system", "content": _SUMMARISE_SYSTEM},
        {"role": "user", "content": text[:4000]},
    ]
    return await _chat(messages)


async def answer(question: str, chunks: list[str], history: list[ChatMessage]) -> str:
    context = "\n\n".join(chunks)
    system = _ANSWER_SYSTEM.format(context=context)
    messages: list[dict] = [{"role": "system", "content": system}]
    for msg in history[-3:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": question})
    return await _chat(messages)


async def _chat(messages: list[dict]) -> str:
    url = f"{settings.ollama_base_url}/api/chat"
    payload = {"model": settings.chat_model, "messages": messages, "stream": False}
    try:
        async with httpx.AsyncClient(timeout=_LLM_TIMEOUT) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()["message"]["content"]
    except httpx.TimeoutException as exc:
        raise LLMError("LLM request timed out") from exc
    except httpx.HTTPStatusError as exc:
        raise LLMError(f"Ollama chat HTTP {exc.response.status_code}") from exc
    except (KeyError, TypeError) as exc:
        raise LLMError("Unexpected response shape from Ollama chat") from exc
