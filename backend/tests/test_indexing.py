from uuid import uuid4

import pytest
from qdrant_client import models

from app.document.chunker import chunk_document
from app.document.schema import Document, IngestionResult
from app.rag.errors import EmbeddingInputError, EmbeddingUnavailable, RetrievalConfigurationError
from app.rag.indexing import EMBEDDING_METADATA_KEY, index_knowledge


@pytest.fixture
def prepared():
    document = Document(id=uuid4(), text="장학 안내\n도서관 안내", source="tests/academic.txt", metadata={"year": 2026})
    return IngestionResult(document=document, chunks=chunk_document(document, str.splitlines))


async def test_embedding_then_existing_collection_upsert_without_payload_change(rag_resources, prepared):
    config, client, provider = rag_resources
    assert await index_knowledge(prepared, client, provider, config) == 2
    provider.embed_documents.assert_awaited_once_with([chunk.text for chunk in prepared.chunks])
    points = client.upsert.await_args.kwargs["points"]
    assert [point.id for point in points] == [str(chunk.id) for chunk in prepared.chunks]
    assert points[0].payload == prepared.chunks[0].model_dump(mode="json", exclude={"id"})
    assert points[0].vector == [1.0] + [0.0] * 383
    client.create_collection.assert_not_awaited()
    client.update_collection.assert_not_awaited()
    client.close.assert_not_awaited()


async def test_new_collection_gets_model_identity(rag_resources, prepared):
    config, client, provider = rag_resources
    client.collection_exists.return_value = False
    client.get_collection.return_value.config.metadata = None
    assert await index_knowledge(prepared, client, provider, config) == 2
    assert client.update_collection.await_args.kwargs["metadata"] == {EMBEDDING_METADATA_KEY: provider.identity}
    client.create_collection.assert_awaited_once()
    client.delete_collection.assert_not_awaited()


@pytest.mark.parametrize("identity", [None, "other-model-same-dimension"])
async def test_existing_unmarked_or_different_model_is_not_adopted(rag_resources, prepared, identity):
    config, client, provider = rag_resources
    client.get_collection.return_value.config.metadata = {EMBEDDING_METADATA_KEY: identity}
    with pytest.raises(RetrievalConfigurationError):
        await index_knowledge(prepared, client, provider, config)
    client.upsert.assert_not_awaited()
    client.update_collection.assert_not_awaited()
    client.delete_collection.assert_not_awaited()


@pytest.mark.parametrize("output", [[], [[1.0]], [[1.0] * 384, [float("nan")] * 384]])
async def test_bad_later_embedding_prevents_all_qdrant_calls(rag_resources, prepared, output):
    config, client, provider = rag_resources
    provider.embed_documents.side_effect = None
    provider.embed_documents.return_value = output
    with pytest.raises(EmbeddingUnavailable):
        await index_knowledge(prepared, client, provider, config)
    client.collection_exists.assert_not_awaited()
    client.create_collection.assert_not_awaited()
    client.upsert.assert_not_awaited()


async def test_token_error_prevents_all_qdrant_calls(rag_resources, prepared):
    config, client, provider = rag_resources
    provider.embed_documents.side_effect = EmbeddingInputError()
    with pytest.raises(EmbeddingInputError):
        await index_knowledge(prepared, client, provider, config)
    client.collection_exists.assert_not_awaited()
    client.upsert.assert_not_awaited()


@pytest.mark.parametrize("changes", [{"qdrant_vector_size": None}, {"qdrant_vector_size": 3}, {"qdrant_distance": models.Distance.DOT}])
async def test_configuration_mismatch_does_not_embed_or_write(rag_resources, prepared, changes):
    config, client, provider = rag_resources
    with pytest.raises(RetrievalConfigurationError):
        await index_knowledge(prepared, client, provider, config.model_copy(update=changes))
    provider.embed_documents.assert_not_awaited()
    client.upsert.assert_not_awaited()


async def test_existing_wrong_dimension_does_not_delete_or_write(rag_resources, prepared):
    config, client, provider = rag_resources
    client.get_collection.return_value.config.params.vectors.size = 2
    with pytest.raises(RetrievalConfigurationError):
        await index_knowledge(prepared, client, provider, config)
    client.upsert.assert_not_awaited()
    client.delete_collection.assert_not_awaited()
