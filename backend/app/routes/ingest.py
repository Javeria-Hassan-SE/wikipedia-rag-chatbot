from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models import IngestRequest, IngestResponse
from app.services import chunker, embedder, llm, scraper, vector_store
from app.services.embedder import EmbedError
from app.services.llm import LLMError
from app.services.scraper import ArticleError

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
async def ingest(request: IngestRequest) -> IngestResponse:
    try:
        article = await scraper.fetch_article(request.url)
    except ArticleError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    chunks = chunker.split(article.body_text)

    try:
        embeddings = await embedder.embed_batch(chunks)
    except EmbedError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    vector_store.recreate_and_insert(chunks, embeddings)

    try:
        summary = await llm.summarise(article.body_text)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return IngestResponse(title=article.title, summary=summary)
