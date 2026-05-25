from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models import ChatRequest, ChatResponse
from app.services import embedder, llm, vector_store
from app.services.embedder import EmbedError
from app.services.llm import LLMError

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    if not vector_store.collection_exists():
        raise HTTPException(
            status_code=400,
            detail="No article loaded. Please ingest an article first.",
        )

    try:
        query_vector = await embedder.embed_single(request.question)
    except EmbedError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    chunks = vector_store.search(query_vector)

    try:
        response_text = await llm.answer(request.question, chunks, request.history)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return ChatResponse(answer=response_text)
