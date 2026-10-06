from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from qdrant_client import AsyncQdrantClient, models

from app.clients.qdrant import ensure_collection, upsert_chunks
from app.core.config import Settings
from app.document.chunker import chunk_document
from app.document.schema import Document


def collection_info(vectors, sparse_vectors=None):
    return SimpleNamespace(config=SimpleNamespace(params=SimpleNamespace(
        vectors=vectors, sparse_vectors=sparse_vectors,
    )))


@pytest.fixture
def qdrant():
    client = AsyncMock(spec=AsyncQdrantClient)
    client.collection_exists.return_value = True
    client.create_collection.return_value = True
    client.get_collection.return_value = collection_info(
        models.VectorParams(size=2, distance=models.Distance.COSINE)
    )
    client.upsert.return_value = models.UpdateResult(
        operation_id=1, status=models.UpdateStatus.COMPLETED
    )
    return client


@pytest.fixture
def chunks():
    document = Document(
        id=uuid4(), text="등록 일정\n장학 안내", source="academic.txt",
        category="academic", metadata={"year": 2026, "tags": ["학사"]},
    )
    return chunk_document(document, str.splitlines)


async def test_missing_collection_is_created_and_checked(qdrant):
    qdrant.collection_exists.return_value = False
    await ensure_collection(qdrant, collection_name="knowledge", vector_size=2)
    qdrant.create_collection.assert_awaited_once_with(
        collection_name="knowledge",
        vectors_config=models.VectorParams(size=2, distance=models.Distance.COSINE),
    )
    qdrant.get_collection.assert_awaited_once_with(collection_name="knowledge")
    qdrant.delete_collection.assert_not_awaited()
    qdrant.close.assert_not_awaited()


async def test_matching_collection_is_reused_with_requested_distance(qdrant):
    qdrant.get_collection.return_value = collection_info(
        models.VectorParams(size=2, distance=models.Distance.DOT)
    )
    await ensure_collection(
        qdrant, collection_name="knowledge", vector_size=2, distance=models.Distance.DOT
    )
    qdrant.create_collection.assert_not_awaited()
    qdrant.delete_collection.assert_not_awaited()


@pytest.mark.parametrize(
    "vectors,sparse_vectors",
    [
        (models.VectorParams(size=3, distance=models.Distance.COSINE), None),
        (models.VectorParams(size=2, distance=models.Distance.DOT), None),
        ({"text": models.VectorParams(size=2, distance=models.Distance.COSINE)}, None),
        (None, {"text": models.SparseVectorParams()}),
        (models.VectorParams(size=2, distance=models.Distance.COSINE), {"text": models.SparseVectorParams()}),
        (models.VectorParams(size=2, distance=models.Distance.COSINE, multivector_config=models.MultiVectorConfig(
            comparator=models.MultiVectorComparator.MAX_SIM
        )), None),
    ],
    ids=["wrong-size", "wrong-distance", "named", "sparse-only", "dense-and-sparse", "multivector"],
)
async def test_incompatible_collection_is_not_deleted_or_recreated(qdrant, vectors, sparse_vectors):
    qdrant.get_collection.return_value = collection_info(vectors, sparse_vectors)
    with pytest.raises(ValueError):
        await ensure_collection(qdrant, collection_name="knowledge", vector_size=2)
    qdrant.create_collection.assert_not_awaited()
    qdrant.delete_collection.assert_not_awaited()


@pytest.mark.parametrize("failed_operation", ["collection_exists", "create_collection", "get_collection"])
async def test_collection_connection_errors_propagate(qdrant, failed_operation):
    qdrant.collection_exists.return_value = failed_operation != "create_collection"
    getattr(qdrant, failed_operation).side_effect = ConnectionError("unavailable")
    with pytest.raises(ConnectionError):
        await ensure_collection(qdrant, collection_name="knowledge", vector_size=2)
    if failed_operation != "create_collection":
        qdrant.create_collection.assert_not_awaited()
    qdrant.delete_collection.assert_not_awaited()


async def test_unsuccessful_collection_creation_is_reported(qdrant):
    qdrant.collection_exists.return_value = False
    qdrant.create_collection.return_value = False
    with pytest.raises(RuntimeError, match="creation did not complete"):
        await ensure_collection(qdrant, collection_name="knowledge", vector_size=2)


@pytest.mark.parametrize("size", [None, 0, -1, True, 2.5])
async def test_invalid_dimensions_do_not_contact_qdrant(qdrant, chunks, size):
    with pytest.raises(ValueError, match="positive integer"):
        await ensure_collection(qdrant, collection_name="knowledge", vector_size=size)
    with pytest.raises(ValueError, match="positive integer"):
        await upsert_chunks(qdrant, chunks, [[1, 0], [0, 1]], collection_name="knowledge", vector_size=size)
    qdrant.collection_exists.assert_not_awaited()
    qdrant.upsert.assert_not_awaited()


@pytest.mark.parametrize("name", ["", " \n"])
async def test_blank_collection_names_do_not_contact_qdrant(qdrant, name):
    with pytest.raises(ValueError, match="collection_name"):
        await ensure_collection(qdrant, collection_name=name, vector_size=2)
    qdrant.collection_exists.assert_not_awaited()


async def test_upsert_maps_ids_vectors_and_payload_and_waits_for_completion(qdrant, chunks):
    vectors = [[1, 0], [0.6, 0.8]]
    count = await upsert_chunks(qdrant, chunks, vectors, collection_name="knowledge", vector_size=2)
    assert count == 2
    request = qdrant.upsert.await_args.kwargs
    assert request["collection_name"] == "knowledge"
    assert request["wait"] is True
    for chunk, vector, point in zip(chunks, vectors, request["points"], strict=True):
        assert point.id == str(chunk.id)
        assert point.vector == vector
        assert point.payload == {
            "document_id": str(chunk.document_id), "chunk_index": chunk.chunk_index,
            "text": chunk.text, "source": "academic.txt", "category": "academic",
            "metadata": {"year": 2026, "tags": ["학사"]},
        }
    await upsert_chunks(qdrant, chunks, vectors, collection_name="knowledge", vector_size=2)
    assert [point.id for point in qdrant.upsert.await_args.kwargs["points"]] == [str(chunk.id) for chunk in chunks]
    qdrant.create_collection.assert_not_awaited()
    qdrant.close.assert_not_awaited()


async def test_empty_upsert_is_a_no_op_without_config_or_network(qdrant):
    assert await upsert_chunks(qdrant, [], [], collection_name="", vector_size=None) == 0
    qdrant.upsert.assert_not_awaited()


@pytest.mark.parametrize("vectors", [[], [[1, 0]], [[1, 0], [0, 1], [1, 1]]])
async def test_vector_count_mismatch_is_rejected(qdrant, chunks, vectors):
    with pytest.raises(ValueError, match="counts must match"):
        await upsert_chunks(qdrant, chunks, vectors, collection_name="knowledge", vector_size=2)
    qdrant.upsert.assert_not_awaited()


async def test_vectors_without_chunks_are_rejected(qdrant):
    with pytest.raises(ValueError, match="counts must match"):
        await upsert_chunks(qdrant, [], [[1, 0]], collection_name="knowledge", vector_size=2)
    qdrant.upsert.assert_not_awaited()


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf"), True, "1", None, 1j, 10**400],
                         ids=["nan", "inf", "negative-inf", "bool", "string", "null", "complex", "overflow"])
async def test_invalid_components_in_a_later_vector_prevent_all_writes(qdrant, chunks, invalid):
    with pytest.raises(ValueError, match="finite real numbers"):
        await upsert_chunks(qdrant, chunks, [[1, 0], [invalid, 1]], collection_name="knowledge", vector_size=2)
    qdrant.upsert.assert_not_awaited()


async def test_wrong_vector_dimension_prevents_all_writes(qdrant, chunks):
    with pytest.raises(ValueError, match="match vector_size"):
        await upsert_chunks(qdrant, chunks, [[1, 0], [1]], collection_name="knowledge", vector_size=2)
    qdrant.upsert.assert_not_awaited()


async def test_upsert_connection_failure_propagates(qdrant, chunks):
    qdrant.upsert.side_effect = ConnectionError("unavailable")
    with pytest.raises(ConnectionError):
        await upsert_chunks(qdrant, chunks, [[1, 0], [0, 1]], collection_name="knowledge", vector_size=2)


@pytest.mark.parametrize("status", [models.UpdateStatus.ACKNOWLEDGED, models.UpdateStatus.WAIT_TIMEOUT])
async def test_unapplied_upsert_is_not_reported_as_success(qdrant, chunks, status):
    qdrant.upsert.return_value = models.UpdateResult(operation_id=1, status=status)
    with pytest.raises(RuntimeError, match="upsert did not complete"):
        await upsert_chunks(qdrant, chunks, [[1, 0], [0, 1]], collection_name="knowledge", vector_size=2)


def test_indexing_settings_are_optional_and_can_be_overridden(settings, monkeypatch):
    assert settings.qdrant_vector_size is None
    monkeypatch.setenv("QDRANT_COLLECTION_NAME", "team_knowledge")
    monkeypatch.setenv("QDRANT_VECTOR_SIZE", "2")
    monkeypatch.setenv("QDRANT_DISTANCE", "Dot")
    overridden = Settings(_env_file=None, DATABASE_URL=str(settings.database_url), QDRANT_URL=str(settings.qdrant_url))
    assert overridden.qdrant_collection_name == "team_knowledge"
    assert overridden.qdrant_vector_size == 2
    assert overridden.qdrant_distance == models.Distance.DOT


@pytest.mark.parametrize("size", [0, -1, "not-an-integer"])
def test_settings_reject_invalid_configured_dimensions(settings, size):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, DATABASE_URL=str(settings.database_url), QDRANT_URL=str(settings.qdrant_url), QDRANT_VECTOR_SIZE=size)
