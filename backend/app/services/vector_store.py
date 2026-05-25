from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.config import settings

COLLECTION_NAME = "article"
VECTOR_DIM = 384


def _get_client() -> QdrantClient:
    return QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)


def recreate_and_insert(chunks: list[str], embeddings: list[list[float]]) -> None:
    client = _get_client()
    if client.collection_exists(COLLECTION_NAME):
        client.delete_collection(COLLECTION_NAME)
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
    )
    points = [
        PointStruct(id=i, vector=vec, payload={"text": chunk})
        for i, (chunk, vec) in enumerate(zip(chunks, embeddings))
    ]
    if points:
        client.upsert(collection_name=COLLECTION_NAME, points=points)


def search(query_vector: list[float], top_k: int = 8) -> list[str]:
    client = _get_client()
    # all-minilm (22MB) produces lower cosine scores than larger models;
    # 0.1 keeps retrieval useful without flooding the prompt with noise.
    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=top_k,
        score_threshold=0.1,
    )
    return [hit.payload["text"] for hit in results]


def collection_exists() -> bool:
    client = _get_client()
    return client.collection_exists(COLLECTION_NAME)
