from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.vector_store import (
    COLLECTION_NAME,
    collection_exists,
    recreate_and_insert,
    search,
)

_FAKE_VECTOR = [0.1] * 384
_PATCH = "app.services.vector_store.QdrantClient"


def _mock_client(exists: bool = False) -> MagicMock:
    client = MagicMock()
    client.collection_exists.return_value = exists
    return client


def test_recreate_and_insert_deletes_existing_collection():
    client = _mock_client(exists=True)
    with patch(_PATCH, return_value=client):
        recreate_and_insert(["chunk"], [_FAKE_VECTOR])

    client.delete_collection.assert_called_once_with(COLLECTION_NAME)


def test_recreate_and_insert_skips_delete_when_collection_absent():
    client = _mock_client(exists=False)
    with patch(_PATCH, return_value=client):
        recreate_and_insert(["chunk"], [_FAKE_VECTOR])

    client.delete_collection.assert_not_called()


def test_recreate_and_insert_always_creates_collection():
    client = _mock_client()
    with patch(_PATCH, return_value=client):
        recreate_and_insert(["chunk"], [_FAKE_VECTOR])

    client.create_collection.assert_called_once()
    call_kwargs = client.create_collection.call_args.kwargs
    assert call_kwargs["collection_name"] == COLLECTION_NAME


def test_recreate_and_insert_upserts_with_text_payload():
    client = _mock_client()
    chunks = ["first chunk", "second chunk"]
    embeddings = [_FAKE_VECTOR, _FAKE_VECTOR]

    with patch(_PATCH, return_value=client):
        recreate_and_insert(chunks, embeddings)

    client.upsert.assert_called_once()
    points = client.upsert.call_args.kwargs["points"]
    assert len(points) == 2
    assert points[0].payload["text"] == "first chunk"
    assert points[1].payload["text"] == "second chunk"
    assert points[0].id == 0
    assert points[1].id == 1


def test_recreate_and_insert_skips_upsert_for_empty_chunks():
    client = _mock_client()
    with patch(_PATCH, return_value=client):
        recreate_and_insert([], [])

    client.upsert.assert_not_called()


def test_search_returns_text_from_payloads():
    hit1, hit2 = MagicMock(), MagicMock()
    hit1.payload = {"text": "relevant passage"}
    hit2.payload = {"text": "another passage"}

    client = _mock_client()
    client.search.return_value = [hit1, hit2]

    with patch(_PATCH, return_value=client):
        results = search(_FAKE_VECTOR, top_k=2)

    assert results == ["relevant passage", "another passage"]
    client.search.assert_called_once_with(
        collection_name=COLLECTION_NAME,
        query_vector=_FAKE_VECTOR,
        limit=2,
        score_threshold=0.1,
    )


def test_search_returns_empty_list_when_no_hits():
    client = _mock_client()
    client.search.return_value = []

    with patch(_PATCH, return_value=client):
        results = search(_FAKE_VECTOR)

    assert results == []


def test_collection_exists_delegates_to_qdrant_client():
    client = _mock_client(exists=True)
    with patch(_PATCH, return_value=client):
        result = collection_exists()

    assert result is True
    client.collection_exists.assert_called_once_with(COLLECTION_NAME)
