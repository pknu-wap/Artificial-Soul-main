import asyncio
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from qdrant_client.http.exceptions import ResponseHandlingException

from app.document.schema import Chunk
from app.rag.embedding import E5EmbeddingProvider
from app.rag.errors import EmbeddingInputError, EmbeddingUnavailable


def point(text="장학 안내", score=0.83, category=None):
    chunk = Chunk(id=uuid4(), document_id=uuid4(), chunk_index=0, text=text,
                  source="scholarship/sample.txt", category=category,
                  metadata={"year": 2026, "tags": ["장학"]})
    return SimpleNamespace(id=str(chunk.id), score=score,
                           payload=chunk.model_dump(mode="json", exclude={"id"}))


async def test_top_k_order_payload_mapping_and_read_only_query(retrieval_client):
    client, qdrant, provider = retrieval_client
    first, second = point(score=0.91), point(text="다른 안내", score=0.75, category="academic")
    qdrant.query_points.return_value = SimpleNamespace(points=[first, second])
    response = await client.post("/api/rag/retrieve", json={"question": " 장학금 질문 ", "top_k": 3})
    assert response.status_code == 200
    body = response.json()
    assert body["question"] == " 장학금 질문 " and body["top_k"] == 3
    assert [hit["chunk_id"] for hit in body["results"]] == [first.id, second.id]
    assert [hit["score"] for hit in body["results"]] == [0.91, 0.75]
    assert body["results"][0] == {
        "chunk_id": first.id, **first.payload, "score": 0.91,
    }
    assert body["results"][0]["category"] is None
    provider.embed_query.assert_awaited_once_with(" 장학금 질문 ")
    call = qdrant.query_points.await_args.kwargs
    assert call["limit"] == 3 and call["with_payload"] is True and call["with_vectors"] is False
    assert "score_threshold" not in call
    assert call["query"] == [1.0] + [0.0] * 383
    qdrant.create_collection.assert_not_awaited()
    qdrant.upsert.assert_not_awaited()
    qdrant.update_collection.assert_not_awaited()
    assert "answer" not in body and "vector" not in body["results"][0]


async def test_empty_collection_is_200_and_default_top_k_is_five(retrieval_client):
    client, _, _ = retrieval_client
    response = await client.post("/api/rag/retrieve", json={"question": "장학금"})
    assert response.status_code == 200
    assert response.json() == {"question": "장학금", "top_k": 5, "results": []}


@pytest.mark.parametrize("body", [
    {}, {"question": ""}, {"question": " \n\t"}, {"question": 123},
    {"question": "x" * 10001}, {"question": "질문", "top_k": 0},
    {"question": "질문", "top_k": 21}, {"question": "질문", "top_k": "5"},
    {"question": "질문", "top_k": True}, {"question": "질문", "unknown": "private-password"},
])
async def test_invalid_request_is_safe_422_without_embedding(retrieval_client, body):
    client, _, provider = retrieval_client
    response = await client.post("/api/rag/retrieve", json=body)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_ERROR"
    assert "private-password" not in response.text
    provider.embed_query.assert_not_awaited()


async def test_token_limit_error_is_422(retrieval_client):
    client, qdrant, provider = retrieval_client
    provider.embed_query.side_effect = EmbeddingInputError()
    response = await client.post("/api/rag/retrieve", json={"question": "긴 질문"})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "EMBEDDING_INPUT_INVALID"
    qdrant.query_points.assert_not_awaited()


@pytest.mark.parametrize("error", [EmbeddingUnavailable(), RuntimeError("private-password@internal-host")])
async def test_embedding_errors_are_safe_503(retrieval_client, error, caplog):
    client, qdrant, provider = retrieval_client
    provider.embed_query.side_effect = error
    response = await client.post("/api/rag/retrieve", json={"question": "질문"})
    assert response.status_code == 503
    assert "private-password" not in response.text + caplog.text
    qdrant.query_points.assert_not_awaited()


async def test_missing_collection_is_503_and_not_created(retrieval_client):
    client, qdrant, _ = retrieval_client
    qdrant.collection_exists.return_value = False
    response = await client.post("/api/rag/retrieve", json={"question": "질문"})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "COLLECTION_NOT_READY"
    qdrant.query_points.assert_not_awaited()
    qdrant.create_collection.assert_not_awaited()


@pytest.mark.parametrize("failure", ["dimension", "distance", "identity"])
async def test_collection_mismatch_is_503_without_search(retrieval_client, failure):
    from qdrant_client import models
    client, qdrant, _ = retrieval_client
    collection = qdrant.get_collection.return_value
    if failure == "dimension":
        collection.config.params.vectors.size = 2
    elif failure == "distance":
        collection.config.params.vectors.distance = models.Distance.DOT
    else:
        collection.config.metadata = {}
    response = await client.post("/api/rag/retrieve", json={"question": "질문"})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "RETRIEVAL_CONFIGURATION_ERROR"
    qdrant.query_points.assert_not_awaited()


async def test_qdrant_connection_error_is_safe_503(retrieval_client, caplog):
    client, qdrant, _ = retrieval_client
    qdrant.query_points.side_effect = ConnectionError("http://secret:private-password@internal-host")
    response = await client.post("/api/rag/retrieve", json={"question": "질문"})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "SEARCH_UNAVAILABLE"
    assert "private-password" not in response.text + caplog.text


async def test_sdk_timeout_wrapper_is_504(retrieval_client):
    client, qdrant, _ = retrieval_client
    qdrant.query_points.side_effect = ResponseHandlingException(httpx.ReadTimeout("private host"))
    response = await client.post("/api/rag/retrieve", json={"question": "질문"})
    assert response.status_code == 504
    assert "private host" not in response.text


@pytest.mark.parametrize("slow", ["embedding", "qdrant"])
async def test_overall_timeout_covers_embedding_and_query(retrieval_client, rag_resources, slow):
    client, qdrant, provider = retrieval_client
    rag_resources[0].retrieval_timeout_seconds = 0.01

    async def never(*args, **kwargs):
        await asyncio.Event().wait()

    if slow == "embedding":
        provider.embed_query.side_effect = never
    else:
        qdrant.query_points.side_effect = never
    response = await asyncio.wait_for(client.post("/api/rag/retrieve", json={"question": "질문"}), timeout=1)
    assert response.status_code == 504
    assert response.json()["detail"]["code"] == "RETRIEVAL_TIMEOUT"


@pytest.mark.parametrize("failure", ["missing-text", "wrong-id", "nan-score", "non-json-metadata", "unknown-field"])
async def test_corrupt_payload_is_safe_500(retrieval_client, failure):
    client, qdrant, _ = retrieval_client
    hit = point()
    if failure == "missing-text":
        del hit.payload["text"]
    elif failure == "wrong-id":
        hit.id = "not-a-uuid"
    elif failure == "nan-score":
        hit.score = float("nan")
    elif failure == "non-json-metadata":
        hit.payload["metadata"] = {"bad": {"set"}}
    else:
        hit.payload["private-password"] = "secret"
    qdrant.query_points.return_value = SimpleNamespace(points=[hit])
    response = await client.post("/api/rag/retrieve", json={"question": "질문"})
    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "RETRIEVAL_DATA_INVALID"
    assert "private-password" not in response.text


async def test_health_and_startup_do_not_load_model_or_index(infrastructure_client, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Health must not load or infer a model")

    monkeypatch.setattr(E5EmbeddingProvider, "_load_sync", forbidden)
    monkeypatch.setattr(E5EmbeddingProvider, "_embed_sync", forbidden)
    client, _, _, qdrant = infrastructure_client
    assert (await client.get("/health")).status_code == 200
    assert (await client.get("/health/ready")).status_code == 200
    qdrant.query_points.assert_not_awaited()
    qdrant.create_collection.assert_not_awaited()
    qdrant.upsert.assert_not_awaited()


async def test_startup_with_missing_model_stays_offline(settings, tmp_path, monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    def forbidden(*args, **kwargs):
        pytest.fail("Startup and Health must not load an embedding model")

    monkeypatch.setattr(E5EmbeddingProvider, "_load_sync", forbidden)
    config = settings.model_copy(update={"embedding_cache_dir": tmp_path})
    application = create_app(config)
    async with application.router.lifespan_context(application):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
            assert (await client.get("/health")).json() == {"status": "ok"}
            assert (await client.get("/docs")).status_code == 200


async def test_missing_real_local_model_is_safe_503(settings, tmp_path):
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    config = settings.model_copy(update={"embedding_cache_dir": tmp_path, "qdrant_vector_size": 384})
    application = create_app(config)
    async with application.router.lifespan_context(application):
        async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
            response = await client.post("/api/rag/retrieve", json={"question": "질문"})
            assert response.status_code == 503
            assert "prepare-model" in response.json()["detail"]["message"]
            assert str(tmp_path) not in response.text
