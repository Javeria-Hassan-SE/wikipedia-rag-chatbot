from __future__ import annotations

import json

import httpx
import pytest
import respx

from app.config import settings
from app.models import ChatMessage
from app.services.llm import LLMError, answer, summarise

_CHAT_URL = f"{settings.ollama_base_url}/api/chat"


def _chat_response(content: str) -> httpx.Response:
    return httpx.Response(200, json={"message": {"role": "assistant", "content": content}})


def _sent_messages(route: respx.Route) -> list[dict]:
    body = json.loads(route.calls[0].request.content)
    return body["messages"]


async def test_summarise_returns_llm_content():
    with respx.mock:
        respx.post(_CHAT_URL).mock(return_value=_chat_response("A brief summary."))
        result = await summarise("Some article text.")

    assert result == "A brief summary."


async def test_summarise_truncates_text_to_4000_chars():
    long_text = "x" * 6000
    with respx.mock:
        route = respx.post(_CHAT_URL).mock(return_value=_chat_response("ok"))
        await summarise(long_text)

    messages = _sent_messages(route)
    user_message = next(m for m in messages if m["role"] == "user")
    assert len(user_message["content"]) == 4000


async def test_summarise_sends_system_message():
    with respx.mock:
        route = respx.post(_CHAT_URL).mock(return_value=_chat_response("ok"))
        await summarise("text")

    messages = _sent_messages(route)
    assert messages[0]["role"] == "system"
    assert "summarisation" in messages[0]["content"].lower()


async def test_answer_injects_chunks_into_system_context():
    chunks = ["Paris is in France.", "The Eiffel Tower is in Paris."]
    with respx.mock:
        route = respx.post(_CHAT_URL).mock(return_value=_chat_response("Paris."))
        await answer("Where is Paris?", chunks, [])

    messages = _sent_messages(route)
    system_content = messages[0]["content"]
    assert "Paris is in France." in system_content
    assert "The Eiffel Tower is in Paris." in system_content


async def test_answer_appends_question_as_final_user_message():
    with respx.mock:
        route = respx.post(_CHAT_URL).mock(return_value=_chat_response("42"))
        await answer("What is the answer?", ["context chunk"], [])

    messages = _sent_messages(route)
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "What is the answer?"


async def test_answer_includes_last_3_history_turns_only():
    history = [
        ChatMessage(role="user", content="q1"),
        ChatMessage(role="assistant", content="a1"),
        ChatMessage(role="user", content="q2"),
        ChatMessage(role="assistant", content="a2"),
        ChatMessage(role="user", content="q3"),
    ]
    with respx.mock:
        route = respx.post(_CHAT_URL).mock(return_value=_chat_response("answer"))
        await answer("current question", ["chunk"], history)

    messages = _sent_messages(route)
    # system + last 3 history + current question = 5
    assert len(messages) == 5
    assert messages[1]["content"] == "q2"
    assert messages[2]["content"] == "a2"
    assert messages[3]["content"] == "q3"
    assert messages[4]["content"] == "current question"


async def test_answer_works_with_empty_history():
    with respx.mock:
        route = respx.post(_CHAT_URL).mock(return_value=_chat_response("answer"))
        await answer("question", ["chunk"], [])

    messages = _sent_messages(route)
    assert len(messages) == 2  # system + user
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


async def test_llm_raises_on_timeout():
    with respx.mock:
        respx.post(_CHAT_URL).mock(side_effect=httpx.TimeoutException("timeout"))
        with pytest.raises(LLMError, match="timed out"):
            await summarise("text")


async def test_llm_raises_on_http_error():
    with respx.mock:
        respx.post(_CHAT_URL).mock(return_value=httpx.Response(503))
        with pytest.raises(LLMError, match="HTTP 503"):
            await summarise("text")


async def test_llm_raises_on_malformed_response():
    with respx.mock:
        respx.post(_CHAT_URL).mock(return_value=httpx.Response(200, json={"done": True}))
        with pytest.raises(LLMError, match="Unexpected response shape"):
            await summarise("text")
